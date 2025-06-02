import discord
from discord.ext import commands
from discord import app_commands
import re
import asyncio
from collections import defaultdict
import datetime
import os
from discord.utils import utcnow
from typing import List

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_history = defaultdict(list)
        self.warning_counts = defaultdict(int)
        self.timeout_history = defaultdict(list)
        self.allowed_roles = [
            1305109844436713512,
            1004989482069676092,
            1318091880650641438,
            981550654382280714
        ]
        self.spam_threshold = 5
        self.spam_timeframe = 5
        self.max_mentions = 5
        self.max_warnings = 3
        self.message_delete_queue = asyncio.Queue()
        
        # ログディレクトリの作成
        self.log_dir = "logs/spam"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # タスクの開始
        self.bot.loop.create_task(self.cleanup_cache())
        self.bot.loop.create_task(self.process_delete_queue())

    def is_recently_timeout(self, user_id: int) -> bool:
        """ユーザーが最近タイムアウトされたかチェック"""
        current_time = utcnow()
        recent_timeouts = [
            timestamp for timestamp in self.timeout_history[user_id]
            if (current_time - timestamp).total_seconds() < 600  # 10分
        ]
        self.timeout_history[user_id] = recent_timeouts
        return len(recent_timeouts) > 0

    async def save_spam_log(self, messages: List[discord.Message], user_id: int):
        """スパムメッセージをログファイルに保存"""
        current_time = utcnow()
        filename = f"{self.log_dir}/spam_detected_{current_time.strftime('%Y%m%d_%H%M%S')}_{user_id}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Spam Detection Log\n")
            f.write(f"User ID: {user_id}\n")
            f.write(f"Detection Time: {current_time}\n")
            f.write(f"Message Count: {len(messages)}\n")
            f.write("-" * 50 + "\n\n")
            
            for msg in sorted(messages, key=lambda x: x.created_at):
                f.write(f"Time: {msg.created_at}\n")
                f.write(f"Channel: #{msg.channel.name}\n")
                f.write(f"Content: {msg.content}\n")
                if msg.attachments:
                    f.write(f"Attachments: {len(msg.attachments)} files\n")
                f.write("-" * 50 + "\n")

    async def handle_spam(self, message: discord.Message):
        user_id = message.author.id
        
        # 既にタイムアウト中なら追加の処理をスキップ
        if self.is_recently_timeout(user_id):
            return

        # タイムアウト履歴を記録
        current_time = utcnow()
        self.timeout_history[user_id].append(current_time)
        
        # 過去10分間のメッセージを収集して削除キューに追加
        ten_minutes_ago = current_time - datetime.timedelta(minutes=10)
        spam_messages = []
        deleted_count = 0
        
        try:
            # まず現在のメッセージを削除キューに追加
            await self.message_delete_queue.put(message)
            deleted_count += 1

            # 他のチャンネルのメッセージを収集
            for channel in message.guild.text_channels:
                try:
                    async for msg in channel.history(after=ten_minutes_ago, limit=None):
                        if msg.author.id == user_id and msg.id != message.id:
                            spam_messages.append(msg)
                            await self.message_delete_queue.put(msg)
                            deleted_count += 1
                            # レート制限を避けるため、10メッセージごとに少し待機
                            if deleted_count % 10 == 0:
                                await asyncio.sleep(2)
                except discord.Forbidden:
                    continue
                except Exception as e:
                    print(f"Error in channel {channel.name}: {e}")
                    continue

            # スパムメッセージをログに記録
            await self.save_spam_log(spam_messages, user_id)
            
            # ユーザーをタイムアウト
            try:
                # タイムアウトの終了時刻を設定（UTCで）
                timeout_end = current_time + datetime.timedelta(minutes=30)
                await message.author.timeout(timeout_end, reason="Spam detection")
                
                await message.channel.send(
                    f"{message.author.mention} のスパムを検出しました。\n"
                    f"{deleted_count}件のメッセージを削除し、30分間のタイムアウトを適用しました。",
                    delete_after=30
                )
            except discord.Forbidden:
                await message.channel.send("タイムアウト処理に必要な権限がありません。", delete_after=10)
            except Exception as e:
                print(f"Error in timeout process: {e}")
                
        except Exception as e:
            print(f"Error in spam handling: {e}")

    async def process_delete_queue(self):
        while True:
            try:
                message = await self.message_delete_queue.get()
                retry_count = 0
                max_retries = 3
                
                while retry_count < max_retries:
                    try:
                        await message.delete()
                        break  # 成功したらループを抜ける
                    except discord.NotFound:
                        break  # メッセージが既に削除されている場合
                    except discord.Forbidden:
                        break  # 権限がない場合
                    except discord.HTTPException as e:
                        if e.code == 429:  # Rate limit
                            retry_after = e.retry_after if hasattr(e, 'retry_after') else 5
                            print(f"Rate limited, waiting {retry_after} seconds...")
                            await asyncio.sleep(retry_after)
                            retry_count += 1
                        else:
                            break
                    except Exception as e:
                        print(f"Unexpected error in delete process: {e}")
                        break
                    
                    await asyncio.sleep(2)  # 各試行の間に待機
                
                self.message_delete_queue.task_done()
                await asyncio.sleep(1)  # キュー処理の間隔
                
            except Exception as e:
                print(f"Error in delete queue processing: {e}")
                await asyncio.sleep(2)

    async def cleanup_cache(self):
        while True:
            await asyncio.sleep(300)  # 5分ごとに実行
            current_time = utcnow()
            for user_id in list(self.message_history.keys()):
                self.message_history[user_id] = [
                    timestamp for timestamp in self.message_history[user_id]
                    if (current_time - timestamp).total_seconds() < self.spam_timeframe
                ]

    def has_allowed_role(self, member: discord.Member) -> bool:
        """許可されたロールを持っているかチェック"""
        return any(role.id in self.allowed_roles for role in member.roles)

    async def check_spam(self, message: discord.Message) -> bool:
        """スパムチェック"""
        user_id = message.author.id
        current_time = utcnow()
        
        self.message_history[user_id].append(current_time)
        self.message_history[user_id] = [
            timestamp for timestamp in self.message_history[user_id]
            if (current_time - timestamp).total_seconds() < self.spam_timeframe
        ]
        
        return len(self.message_history[user_id]) >= self.spam_threshold

    def contains_invite_link(self, content: str) -> bool:
        """招待リンクを含むかチェック"""
        invite_pattern = r'(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discordapp\.com/invite)/[a-zA-Z0-9]+'
        return bool(re.search(invite_pattern, content))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """メッセージ受信時の処理"""
        if message.author.bot or isinstance(message.channel, discord.DMChannel):
            return

        if isinstance(message.author, discord.Member) and self.has_allowed_role(message.author):
            return

        if self.contains_invite_link(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} サーバーの招待リンクの投稿は許可されていません。",
                    delete_after=10
                )
                return
            except discord.NotFound:
                pass

        if await self.check_spam(message):
            await self.handle_spam(message)
            return

        if len(message.mentions) > self.max_mentions:
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} 過度なメンションの使用は禁止されています。",
                    delete_after=10
                )
            except discord.NotFound:
                pass

    @app_commands.command(name="x-spam-settings")
    @app_commands.default_permissions(administrator=True)
    async def spam_settings(self, interaction: discord.Interaction):
        """現在のスパム対策設定を表示します"""
        embed = discord.Embed(
            title="スパム対策設定",
            color=discord.Color.blue(),
            timestamp=utcnow()
        )
        
        embed.add_field(
            name="スパム判定閾値",
            value=f"{self.spam_timeframe}秒間に{self.spam_threshold}メッセージ",
            inline=False
        )
        embed.add_field(
            name="最大メンション数",
            value=f"1メッセージあたり{self.max_mentions}人まで",
            inline=False
        )
        embed.add_field(
            name="タイムアウト期間",
            value="30分",
            inline=False
        )
        embed.add_field(
            name="メッセージ削除期間",
            value="過去10分間",
            inline=False
        )
        
        allowed_roles = [f"<@&{role_id}>" for role_id in self.allowed_roles]
        embed.add_field(
            name="除外ロール",
            value="\n".join(allowed_roles),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
    try:
        await bot.tree.sync()
        print("Synced all commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
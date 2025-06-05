import discord
from discord.ext import commands
from discord import app_commands, Interaction, TextChannel, User, Forbidden, HTTPException
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Tuple, Optional, Dict
import io

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.admin')

    async def get_logging_cog(self) -> commands.Cog:
        """LoggingCogを取得"""
        return self.bot.get_cog('LoggingCog')

    @app_commands.command(name="setlogch", description="一般ログチャンネルを設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def setlogch(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        一般ログチャンネルを設定するコマンド
        
        Parameters
        ----------
        interaction : discord.Interaction
            コマンドのインタラクション
        channel : discord.TextChannel
            設定するログチャンネル
        """
        try:
            # ギルドIDを文字列として取得
            guild_id = str(interaction.guild_id)
            
            # ギルド設定が存在しない場合は初期化
            if not self.bot.config_manager.has_guild(guild_id):
                self.bot.config_manager.initialize_guild(guild_id)
            
            # チャンネルIDを設定
            update_data = {
                'log_channel': channel.id
            }
            
            # 設定を更新
            success = self.bot.config_manager.update_guild_config(guild_id, update_data)
            
            if success:
                await interaction.response.send_message(
                    f"✅ 一般ログチャンネルを {channel.mention} に設定しました。",
                    ephemeral=True
                )
                self.logger.info(f"Log channel set to {channel.id} for guild {guild_id}")
            else:
                raise Exception("Failed to save configuration")
                
        except Exception as e:
            self.logger.error(f"Error in setlogch: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 設定中にエラーが発生しました。管理者に連絡してください。",
                ephemeral=True
            )

    @app_commands.command(name="setvclogch", description="VC専用ログチャンネルを設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def setvclogch(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        VC専用ログチャンネルを設定するコマンド
        
        Parameters
        ----------
        interaction : discord.Interaction
            コマンドのインタラクション
        channel : discord.TextChannel
            設定するVCログチャンネル
        """
        try:
            # ギルドIDを文字列として取得
            guild_id = str(interaction.guild_id)
            
            # ギルド設定が存在しない場合は初期化
            if not self.bot.config_manager.has_guild(guild_id):
                self.bot.config_manager.initialize_guild(guild_id)
            
            # チャンネルIDを設定
            update_data = {
                'vc_log_channel': channel.id
            }
            
            # 設定を更新
            success = self.bot.config_manager.update_guild_config(guild_id, update_data)
            
            if success:
                await interaction.response.send_message(
                    f"✅ VC専用ログチャンネルを {channel.mention} に設定しました。",
                    ephemeral=True
                )
                self.logger.info(f"VC log channel set to {channel.id} for guild {guild_id}")
            else:
                raise Exception("Failed to save configuration")
                
        except Exception as e:
            self.logger.error(f"Error in setvclogch: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 設定中にエラーが発生しました。管理者に連絡してください。",
                ephemeral=True
            )

    @app_commands.command(name="viewlogch", description="現在のログチャンネル設定を表示")
    @app_commands.checks.has_permissions(administrator=True)
    async def viewlogch(self, interaction: discord.Interaction):
        """現在のログチャンネル設定を表示するコマンド"""
        try:
            guild_id = str(interaction.guild_id)
            guild_config = self.bot.config_manager.get_guild_config(guild_id)
            
            if not guild_config:
                await interaction.response.send_message(
                    "❌ このサーバーの設定が見つかりません。",
                    ephemeral=True
                )
                return
            
            # 各チャンネルの情報を取得
            log_channel_id = guild_config.get('log_channel')
            vc_log_channel_id = guild_config.get('vc_log_channel')
            
            # レスポンスメッセージを構築
            response = "📋 **現在のログチャンネル設定**\n\n"
            
            if log_channel_id:
                channel = interaction.guild.get_channel(log_channel_id)
                response += f"一般ログチャンネル: {channel.mention if channel else '未設定'}\n"
            else:
                response += "一般ログチャンネル: 未設定\n"
                
            if vc_log_channel_id:
                channel = interaction.guild.get_channel(vc_log_channel_id)
                response += f"VC専用ログチャンネル: {channel.mention if channel else '未設定'}"
            else:
                response += "VC専用ログチャンネル: 未設定"
            
            await interaction.response.send_message(response, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error in viewlogch: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 設定の取得中にエラーが発生しました。",
                ephemeral=True
            )

    async def create_delete_log_file(self, messages: List[discord.Message], deleted_by: discord.Member) -> discord.File:
        """削除されたメッセージのログファイルを作成"""
        # 日本時間のタイムゾーン
        JST = timezone(timedelta(hours=9))
        
        content = []
        content.append(f"=== メッセージ削除ログ ===")
        content.append(f"削除実行者: {deleted_by.name} ({deleted_by.id})")
        content.append(f"削除日時: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')} JST")
        content.append(f"削除数: {len(messages)}")
        content.append("=" * 50)
        content.append("")
        
        for msg in sorted(messages, key=lambda x: x.created_at):
            # メッセージの投稿日時を日本時間に変換
            msg_time_jst = msg.created_at.replace(tzinfo=timezone.utc).astimezone(JST)
            timestamp = msg_time_jst.strftime("%Y-%m-%d %H:%M:%S")
            
            author = f"{msg.author.name}#{msg.author.discriminator}"
            content.append(f"[{timestamp} JST] {author} ({msg.author.id})")
            if msg.content:
                content.append(f"内容: {msg.content}")
            if msg.attachments:
                content.append("添付ファイル:")
                for attachment in msg.attachments:
                    content.append(f"  - {attachment.filename} ({attachment.size} bytes)")
                    content.append(f"    URL: {attachment.url}")
            content.append("-" * 30)
            content.append("")
        
        content_text = "\n".join(content)
        return discord.File(
            io.StringIO(content_text),
            filename=f"deleted_messages_{datetime.now(JST).strftime('%Y%m%d_%H%M%S')}.txt"
        )

    async def send_delete_log_with_images(self, interaction: discord.Interaction, messages: List[discord.Message], 
                                         saved_images: List[dict], delete_type: str, 
                                         target_user: Optional[discord.User] = None,
                                         scope: Optional[str] = None):
        """削除ログを送信（保存した画像データと共に）"""
        logging_cog = await self.get_logging_cog()
        if not logging_cog:
            return
        
        # 日本時間のタイムゾーン
        JST = timezone(timedelta(hours=9))
        
        embed = discord.Embed(
            title="メッセージ削除ログ",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # 削除実行者
        embed.add_field(
            name="実行者",
            value=f"{interaction.user.mention} ({interaction.user.name})",
            inline=True
        )
        
        # 削除タイプ
        if delete_type == "bulk":
            embed.add_field(name="削除タイプ", value="一括削除", inline=True)
        elif delete_type == "user":
            embed.add_field(
                name="削除タイプ", 
                value=f"ユーザー指定削除 ({'グローバル' if scope == 'global' else 'チャンネル内'})",
                inline=True
            )
        
        # 削除対象ユーザー（user削除の場合）
        if target_user:
            embed.add_field(
                name="対象ユーザー",
                value=f"{target_user.mention} ({target_user.name})",
                inline=True
            )
        
        # チャンネル情報
        if scope == "global" and messages:
            # グローバル削除の場合、影響を受けたチャンネルをリスト
            channels = list(set(msg.channel for msg in messages))
            channel_mentions = [f"{ch.mention}" for ch in channels[:5]]  # 最大5つまで表示
            if len(channels) > 5:
                channel_mentions.append(f"他 {len(channels) - 5} チャンネル")
            embed.add_field(
                name="影響チャンネル",
                value="\n".join(channel_mentions),
                inline=False
            )
        else:
            # 特定チャンネルでの削除
            embed.add_field(
                name="チャンネル",
                value=f"{interaction.channel.mention}\n[ジャンプ]({interaction.channel.jump_url})",
                inline=True
            )
        
        # 削除数
        embed.add_field(
            name="削除メッセージ数",
            value=f"{len(messages)} 件",
            inline=True
        )
        
        # ログファイルを作成
        log_file = await self.create_delete_log_file(messages, interaction.user)
        
        # ログチャンネルを取得
        log_channel = await logging_cog.get_log_channel(interaction.guild_id)
        if not log_channel:
            return
            
        # メインのログを送信
        await log_channel.send(embed=embed, file=log_file)
        
        # 保存した画像をログチャンネルに送信
        if saved_images:
            # 画像をまとめて送信（最大10ファイルまで）
            image_files = []
            for i, img_info in enumerate(saved_images[:10]):
                file = discord.File(
                    io.BytesIO(img_info['data']),
                    filename=f"{i}_{img_info['filename']}"
                )
                image_files.append(file)
            
            if image_files:
                await log_channel.send(
                    content="**削除されたメッセージに含まれていた画像:**",
                    files=image_files
                )
                
                # 10個を超える画像がある場合は通知
                if len(saved_images) > 10:
                    await log_channel.send(f"*他に {len(saved_images) - 10} 個の画像がありました（ログファイルを参照）*")
        
        # アーカイブチャンネルへの保存
        archive_channel = logging_cog.get_archive_channel()
        if archive_channel and saved_images:
            for img_info in saved_images:
                try:
                    msg = img_info['message']
                    
                    # アーカイブ用のEmbed作成
                    archive_embed = discord.Embed(
                        title="管理コマンドで削除された画像",
                        color=discord.Color.blue(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    archive_embed.add_field(
                        name="削除実行者",
                        value=f"{interaction.user.name} (`{interaction.user.id}`)",
                        inline=False
                    )
                    archive_embed.add_field(
                        name="元のサーバー",
                        value=f"{msg.guild.name} (`{msg.guild.id}`)",
                        inline=False
                    )
                    archive_embed.add_field(
                        name="元のチャンネル",
                        value=f"#{msg.channel.name} (`{msg.channel.id}`)",
                        inline=False
                    )
                    archive_embed.add_field(
                        name="元の投稿者",
                        value=f"{msg.author.name} (`{msg.author.id}`)",
                        inline=False
                    )
                    
                    # 画像ファイルを作成
                    file = discord.File(
                        io.BytesIO(img_info['data']),
                        filename=img_info['filename']
                    )
                    
                    # アーカイブチャンネルに送信
                    await archive_channel.send(embed=archive_embed, file=file)
                    
                except Exception as e:
                    self.logger.error(f"Error archiving image: {e}")
    
    async def send_delete_log(self, interaction: discord.Interaction, messages: List[discord.Message], 
                            delete_type: str, target_user: Optional[discord.User] = None,
                            scope: Optional[str] = None):
        """削除ログを送信（画像なしの場合）"""
        await self.send_delete_log_with_images(interaction, messages, [], delete_type, target_user, scope)

    @app_commands.command(name="delete", description="指定した数のメッセージを削除")
    @app_commands.describe(amount="削除するメッセージ数")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction: discord.Interaction, amount: int):
        """指定した数のメッセージを削除"""
        if amount <= 0 or amount > 100:
            await interaction.response.send_message("削除数は1〜100の間で指定してください。", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # LoggingCogを取得して、一時的に削除ログを無効化
            logging_cog = await self.get_logging_cog()
            if logging_cog:
                # 削除コマンドのフラグを立てる
                logging_cog._admin_delete_in_progress = True
            
            # メッセージを取得（コマンド自体は含まない）
            messages = []
            async for message in interaction.channel.history(limit=amount):
                messages.append(message)
            
            if not messages:
                await interaction.followup.send("削除するメッセージが見つかりませんでした。", ephemeral=True)
                return
            
            # 削除前に画像データを保存
            saved_images = []
            for msg in messages:
                if msg.attachments:
                    for attachment in msg.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            try:
                                # 画像データをダウンロード
                                img_data = await attachment.read()
                                saved_images.append({
                                    'data': img_data,
                                    'filename': attachment.filename,
                                    'message': msg,
                                    'attachment': attachment
                                })
                            except Exception as e:
                                self.logger.error(f"Failed to save image before deletion: {e}")
            
            # メッセージを削除
            deleted_count = 0
            deleted_messages = []
            for message in messages:
                try:
                    await message.delete()
                    deleted_messages.append(message)
                    deleted_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to delete message: {e}")
            
            # ログを送信（保存した画像データと共に）
            if deleted_count > 0:
                await self.send_delete_log_with_images(interaction, deleted_messages, saved_images, "bulk")
            
            # 結果を報告
            await interaction.followup.send(
                f"✅ {deleted_count}件のメッセージを削除しました。",
                ephemeral=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in delete command: {e}")
            await interaction.followup.send(
                "❌ メッセージの削除中にエラーが発生しました。",
                ephemeral=True
            )
        finally:
            # フラグをリセット
            if logging_cog:
                logging_cog._admin_delete_in_progress = False

    @app_commands.command(name="userdelete", description="指定したユーザーのメッセージを削除")
    @app_commands.describe(
        user="対象ユーザー",
        amount="削除するメッセージ数",
        scope="削除範囲（global: サーバー全体, normal: このチャンネルのみ）"
    )
    @app_commands.choices(scope=[
        app_commands.Choice(name="このチャンネルのみ", value="normal"),
        app_commands.Choice(name="サーバー全体", value="global")
    ])
    @app_commands.checks.has_permissions(manage_messages=True)
    async def userdelete(self, interaction: discord.Interaction, user: discord.User, amount: int, scope: str = "normal"):
        """指定したユーザーのメッセージを削除"""
        if amount <= 0 or amount > 100:
            await interaction.response.send_message("削除数は1〜100の間で指定してください。", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # LoggingCogを取得して、一時的に削除ログを無効化
            logging_cog = await self.get_logging_cog()
            if logging_cog:
                # 削除コマンドのフラグを立てる
                logging_cog._admin_delete_in_progress = True
            
            messages_to_delete = []
            
            if scope == "normal":
                # このチャンネルのみ
                async for message in interaction.channel.history(limit=None):
                    if message.author.id == user.id:
                        messages_to_delete.append(message)
                        if len(messages_to_delete) >= amount:
                            break
            else:
                # サーバー全体
                for channel in interaction.guild.text_channels:
                    if len(messages_to_delete) >= amount:
                        break
                    
                    try:
                        async for message in channel.history(limit=None):
                            if message.author.id == user.id:
                                messages_to_delete.append(message)
                                if len(messages_to_delete) >= amount:
                                    break
                    except discord.Forbidden:
                        continue
            
            if not messages_to_delete:
                await interaction.followup.send(
                    f"{user.mention} のメッセージが見つかりませんでした。",
                    ephemeral=True
                )
                return
            
            # 最新のものから指定数だけ取得
            messages_to_delete = sorted(messages_to_delete, key=lambda x: x.created_at, reverse=True)[:amount]
            
            # 削除前に画像データを保存
            saved_images = []
            for msg in messages_to_delete:
                if msg.attachments:
                    for attachment in msg.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            try:
                                # 画像データをダウンロード
                                img_data = await attachment.read()
                                saved_images.append({
                                    'data': img_data,
                                    'filename': attachment.filename,
                                    'message': msg,
                                    'attachment': attachment
                                })
                            except Exception as e:
                                self.logger.error(f"Failed to save image before deletion: {e}")
            
            # メッセージを削除
            deleted_count = 0
            deleted_messages = []
            for message in messages_to_delete:
                try:
                    await message.delete()
                    deleted_messages.append(message)
                    deleted_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to delete message: {e}")
            
            # ログを送信（保存した画像データと共に）
            if deleted_count > 0:
                await self.send_delete_log_with_images(interaction, deleted_messages, saved_images, "user", target_user=user, scope=scope)
            
            # 結果を報告
            scope_text = "サーバー全体" if scope == "global" else "このチャンネル"
            await interaction.followup.send(
                f"✅ {scope_text}から {user.mention} のメッセージを{deleted_count}件削除しました。",
                ephemeral=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in userdelete command: {e}")
            await interaction.followup.send(
                "❌ メッセージの削除中にエラーが発生しました。",
                ephemeral=True
            )
        finally:
            # フラグをリセット
            if logging_cog:
                logging_cog._admin_delete_in_progress = False

    @app_commands.command(name="addword", description="禁止ワードを追加")
    @app_commands.checks.has_permissions(administrator=True)
    async def addword(self, interaction: discord.Interaction, word: str):
        try:
            guild_config = self.bot.config_manager.get_guild_config(str(interaction.guild_id))
            if not guild_config:
                guild_config = {'banned_words': []}
            elif 'banned_words' not in guild_config:
                guild_config['banned_words'] = []

            if word not in guild_config['banned_words']:
                guild_config['banned_words'].append(word)
                self.bot.config_manager.update_guild_config(str(interaction.guild_id), guild_config)
                await interaction.response.send_message(f"禁止ワード「{word}」を追加しました。")
            else:
                await interaction.response.send_message("そのワードは既に禁止リストに含まれています。")
        except Exception as e:
            self.logger.error(f"Error in addword: {e}")
            await interaction.response.send_message("設定中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="removeword", description="禁止ワードを削除")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeword(self, interaction: discord.Interaction, word: str):
        try:
            guild_config = self.bot.config_manager.get_guild_config(str(interaction.guild_id))
            if guild_config and 'banned_words' in guild_config and word in guild_config['banned_words']:
                guild_config['banned_words'].remove(word)
                self.bot.config_manager.update_guild_config(str(interaction.guild_id), guild_config)
                await interaction.response.send_message(f"禁止ワード「{word}」を削除しました。")
            else:
                await interaction.response.send_message("そのワードは禁止リストに含まれていません。")
        except Exception as e:
            self.logger.error(f"Error in removeword: {e}")
            await interaction.response.send_message("設定中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="setspam", description="スパム設定を変更")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(setting=[
        app_commands.Choice(name="count", value="count"),
        app_commands.Choice(name="time", value="time"),
        app_commands.Choice(name="action", value="action"),
        app_commands.Choice(name="timeout", value="timeout")
    ])
    async def setspam(self, interaction: discord.Interaction, setting: str, value: str):
        try:
            guild_config = self.bot.config_manager.get_guild_config(str(interaction.guild_id))
            if not guild_config:
                guild_config = {
                    'spam_settings': {
                        'message_count': 5,
                        'time_window': 5,
                        'action': 'timeout',
                        'timeout_duration': 300
                    }
                }
            elif 'spam_settings' not in guild_config:
                guild_config['spam_settings'] = {
                    'message_count': 5,
                    'time_window': 5,
                    'action': 'timeout',
                    'timeout_duration': 300
                }

            if setting == 'action' and value not in ['timeout', 'delete', 'ban']:
                await interaction.response.send_message("Invalid action. Use: timeout, delete, or ban", ephemeral=True)
                return

            try:
                if setting != 'action':
                    value = int(value)
                    if value <= 0:
                        raise ValueError
            except ValueError:
                await interaction.response.send_message("Please provide a valid positive number.", ephemeral=True)
                return

            setting_mapping = {
                'count': 'message_count',
                'time': 'time_window',
                'action': 'action',
                'timeout': 'timeout_duration'
            }

            guild_config['spam_settings'][setting_mapping[setting]] = value
            self.bot.config_manager.update_guild_config(str(interaction.guild_id), guild_config)
            await interaction.response.send_message(f"Spam setting '{setting}' has been updated to: {value}")
        except Exception as e:
            self.logger.error(f"Error in setspam: {e}")
            await interaction.response.send_message("設定中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="wordlist", description="禁止ワードリストを表示")
    @app_commands.checks.has_permissions(administrator=True)
    async def wordlist(self, interaction: discord.Interaction):
        try:
            guild_config = self.bot.config_manager.get_guild_config(str(interaction.guild_id))
            banned_words = guild_config.get('banned_words', []) if guild_config else []

            if not banned_words:
                await interaction.response.send_message("禁止ワードリストは空です。")
                return

            embed = discord.Embed(
                title="禁止ワードリスト",
                color=discord.Color.red()
            )
            
            for i in range(0, len(banned_words), 10):
                chunk = banned_words[i:i+10]
                embed.add_field(
                    name=f"禁止ワード {i+1}-{i+len(chunk)}",
                    value="\n".join(chunk),
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            self.logger.error(f"Error in wordlist: {e}")
            await interaction.response.send_message("リスト取得中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="serverstats", description="サーバー統計を表示")
    @app_commands.checks.has_permissions(administrator=True)
    async def serverstats(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            total_members = guild.member_count
            bot_count = len([m for m in guild.members if m.bot])
            human_count = total_members - bot_count
            
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            
            roles = len(guild.roles) - 1
            
            cursor = self.bot.db.cursor
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT SUM(message_count) 
                FROM message_stats 
                WHERE guild_id = ? AND date = ?
            ''', (guild.id, today))
            today_messages = cursor.fetchone()[0] or 0
            
            cursor.execute('''
                SELECT SUM(message_count) 
                FROM message_stats 
                WHERE guild_id = ? AND date >= date('now', '-7 days')
            ''', (guild.id,))
            week_messages = cursor.fetchone()[0] or 0
            
            embed = discord.Embed(
                title=f"{guild.name} の統計情報",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(
                name="メンバー情報",
                value=f"総メンバー数: {total_members}\n"
                      f"ユーザー: {human_count}\n"
                      f"ボット: {bot_count}",
                inline=False
            )
            
            embed.add_field(
                name="チャンネル情報",
                value=f"テキストチャンネル: {text_channels}\n"
                      f"ボイスチャンネル: {voice_channels}\n"
                      f"カテゴリー: {categories}",
                inline=False
            )
            
            embed.add_field(
                name="役職",
                value=f"総役職数: {roles}",
                inline=False
            )
            
            embed.add_field(
                name="アクティビティ",
                value=f"今日のメッセージ: {today_messages}\n"
                      f"週間メッセージ: {week_messages}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            self.logger.error(f"Error in serverstats: {e}")
            await interaction.response.send_message("統計情報の取得中にエラーが発生しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

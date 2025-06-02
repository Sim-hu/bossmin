import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import json
from typing import Union, List, Optional
import asyncio

class Archive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.archive_channel = {}
        self.allowed_users = set()
        self.allowed_roles = set()
        self.load_permissions()
        self.load_archive_channels()
        self.bot_id = 1305765130579083345  # ボットのユーザーID

    def load_permissions(self):
        try:
            with sqlite3.connect('bot_statistics.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS archive_permissions
                (guild_id TEXT, user_id TEXT, role_id TEXT)
                ''')
                cursor.execute('SELECT guild_id, user_id, role_id FROM archive_permissions')
                for row in cursor.fetchall():
                    if row[1]:
                        self.allowed_users.add(int(row[1]))
                    if row[2]:
                        self.allowed_roles.add(int(row[2]))
        except Exception as e:
            print(f"権限の読み込み中にエラーが発生しました: {e}")

    def load_archive_channels(self):
        try:
            with sqlite3.connect('bot_statistics.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS archive_channels
                (guild_id TEXT, channel_id TEXT)
                ''')
                cursor.execute('SELECT guild_id, channel_id FROM archive_channels')
                for row in cursor.fetchall():
                    self.archive_channel[int(row[0])] = int(row[1])
        except Exception as e:
            print(f"アーカイブチャンネルの読み込み中にエラーが発生しました: {e}")

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        
        if interaction.user.guild_permissions.administrator:
            return True
            
        if any(role.id in self.allowed_roles for role in interaction.user.roles):
            return True
            
        if interaction.user.id in self.allowed_users:
            return True
            
        return False

    async def tag_autocomplete(
            self,
            interaction: discord.Interaction,
            current: str,
        ) -> List[app_commands.Choice[str]]:
            # フォーラムチャンネルを取得
            channel = None
            try:
                if hasattr(interaction.namespace, 'forum_channel'):
                    # フォーラムチャンネルパラメータを直接参照
                    channel_id = getattr(interaction.namespace, 'forum_channel', None)
                    if isinstance(channel_id, int):
                        channel = interaction.client.get_channel(channel_id) or await interaction.client.fetch_channel(channel_id)
                    else:
                        channel = channel_id
            except Exception as e:
                print(f"タグの自動補完でエラーが発生しました: {e}")
                return []

            if not channel or not isinstance(channel, discord.ForumChannel):
                return []

            # 利用可能なタグを取得
            available_tags = channel.available_tags
            if not available_tags:
                return []

            # 現在のタグ入力を解析
            current_tags = [tag.strip() for tag in current.split(',') if tag.strip()]
            last_tag = current_tags[-1] if current_tags else ''
            
            # マッチするタグをフィルタリング
            matching_tags = []
            for tag in available_tags:
                if last_tag.lower() in tag.name.lower():
                    matching_tags.append(tag)
                    if len(matching_tags) >= 25:  # Discord APIの制限
                        break
            
            # 選択肢を構築
            choices = []
            for tag in matching_tags:
                # 最後のタグを新しいタグに置き換える
                new_tags = current_tags[:-1] + [tag.name] if current_tags else [tag.name]
                value = ','.join(new_tags)
                choices.append(app_commands.Choice(name=tag.name, value=value))
            
            return choices

    @app_commands.command(name="a-cancmd", description="コマンドの使用権限を設定します")
    @app_commands.describe(
        target="権限を付与するロールまたはユーザー"
    )
    async def add_command_permission(self, interaction: discord.Interaction, target: Union[discord.Role, discord.Member]):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return

        try:
            with sqlite3.connect('bot_statistics.db') as conn:
                cursor = conn.cursor()
                if isinstance(target, discord.Role):
                    self.allowed_roles.add(target.id)
                    cursor.execute('INSERT INTO archive_permissions (guild_id, role_id) VALUES (?, ?)',
                                 (str(interaction.guild_id), str(target.id)))
                else:
                    self.allowed_users.add(target.id)
                    cursor.execute('INSERT INTO archive_permissions (guild_id, user_id) VALUES (?, ?)',
                                 (str(interaction.guild_id), str(target.id)))
                conn.commit()
            
            await interaction.response.send_message(
                f"{'ロール' if isinstance(target, discord.Role) else 'ユーザー'} {target.name} に権限を付与しました。"
            )
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)

    @app_commands.command(name="f-arc", description="指定したスレッドまたはチャンネルをフォーラムチャンネルに転送します")
    @app_commands.describe(
        source_id="転送するスレッドまたはチャンネルのID",
        forum_channel="転送先のフォーラムチャンネル",
        tags="適用するタグ（カンマ区切りで複数選択可）"
    )
    @app_commands.autocomplete(tags=tag_autocomplete)
    async def forum_archive_thread(
        self,
        interaction: discord.Interaction,
        source_id: str,
        forum_channel: discord.ForumChannel,
        tags: str = ""
    ):
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("このコマンドを使用する権限がありません。", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            source_id = int(source_id)
            source = await self.bot.fetch_channel(source_id)

            if not source:
                await interaction.followup.send("無効なチャンネルまたはスレッドIDです。")
                return

            # タグの処理
            applied_tags = []
            if tags:
                tag_names = [t.strip() for t in tags.split(',') if t.strip()]
                available_tags = forum_channel.available_tags
                for tag_name in tag_names:
                    matching_tag = discord.utils.get(available_tags, name=tag_name)
                    if matching_tag:
                        applied_tags.append(matching_tag)

            # タグが必須かどうかを安全に確認
            required_tags = False
            try:
                required_tags = forum_channel.required_tags
            except AttributeError:
                # required_tags属性がない場合はFalseとする
                pass

            if required_tags and not applied_tags:
                available_tags_str = ", ".join([tag.name for tag in forum_channel.available_tags[:10]])
                await interaction.followup.send(
                    f"このフォーラムではタグの指定が必須です。以下のようなタグから選択してください: {available_tags_str}..."
                )
                return

            if isinstance(source, discord.Thread):
                # スレッドからフォーラムへの転送
                new_thread = await forum_channel.create_thread(
                    name=f"転送: {source.name}",
                    content=f"元スレッド: {source.jump_url}",
                    applied_tags=applied_tags,
                    auto_archive_duration=10080
                )
                
                messages = [message async for message in source.history(limit=None, oldest_first=True)]
            elif isinstance(source, discord.TextChannel):
                # テキストチャンネルからフォーラムへの転送
                new_thread = await forum_channel.create_thread(
                    name=f"転送: {source.name}",
                    content=f"元チャンネル: {source.jump_url}",
                    applied_tags=applied_tags,
                    auto_archive_duration=10080
                )
                
                messages = [message async for message in source.history(limit=100, oldest_first=True)]
            elif isinstance(source, discord.ForumChannel):
                # フォーラムチャンネルからフォーラムへの転送
                await interaction.followup.send("フォーラムチャンネル全体の転送はサポートされていません。特定のスレッドIDを指定してください。")
                return
            else:
                await interaction.followup.send("このタイプのチャンネルからの転送はサポートされていません。")
                return

            total_messages = len(messages)
            message_count = 0

            for message in messages:
                # 送信者情報を先に設定
                embed = discord.Embed(
                    color=discord.Color.blue(),
                    timestamp=message.created_at
                )

                embed.set_author(
                    name=f"{message.author.display_name} ({message.author.name})",
                    icon_url=message.author.display_avatar.url
                )
                
                # 添付ファイルの情報を設定
                files = []
                if message.attachments:
                    for attachment in message.attachments:
                        try:
                            file = await attachment.to_file()
                            files.append(file)
                        except:
                            # 添付ファイルの取得に失敗した場合はスキップ
                            pass
                            
                    if files:
                        embed.add_field(
                            name="📎 添付ファイル",
                            value=f"{len(files)}件",
                            inline=False
                        )

                # メッセージ内容を最後に設定
                if message.content:
                    embed.description = message.content

                embed.set_footer(text=f"メッセージ {message_count + 1}/{total_messages}")

                # 送信用の埋め込みオブジェクトリスト
                embeds_to_send = [embed] + message.embeds

                try:
                    await new_thread.thread.send(
                        embeds=embeds_to_send,
                        files=files
                    )
                except Exception as e:
                    print(f"メッセージ送信エラー: {e}")

                message_count += 1
                await asyncio.sleep(1)  # レート制限を避けるための遅延

            summary_embed = discord.Embed(
                title="転送完了",
                description=f"合計 {total_messages} メッセージを転送しました。",
                color=discord.Color.green()
            )
            await new_thread.thread.send(embed=summary_embed)
            await interaction.followup.send(
                f"チャンネル/スレッドを {new_thread.thread.mention} に転送しました。\n"
                f"合計 {total_messages} メッセージをコピーしました。"
            )

        except ValueError:
            await interaction.followup.send("無効なIDです。数値を入力してください。")
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {e}")

    @app_commands.command(name="f-rename", description="Botが作成したスレッドの名前を変更します")
    @app_commands.describe(
        thread="名前を変更するスレッド",
        new_name="新しいスレッド名"
    )
    async def rename_thread(
        self,
        interaction: discord.Interaction,
        thread: discord.Thread,
        new_name: str
    ):
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("このコマンドを使用する権限がありません。", ephemeral=True)
            return

        try:
            # スレッドの作成者を確認
            thread_owner = await self.get_thread_owner(thread)
            
            if thread_owner == self.bot_id:
                await thread.edit(name=new_name)
                await interaction.response.send_message(f"スレッド名を「{new_name}」に変更しました。")
            else:
                await interaction.response.send_message("Botが作成したものではないため変更できません。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)

    @app_commands.command(name="f-idrename", description="スレッドIDを指定してBotが作成したスレッドの名前を変更します")
    @app_commands.describe(
        thread_id="名前を変更するスレッドのID",
        new_name="新しいスレッド名"
    )
    async def idrename_thread(
        self,
        interaction: discord.Interaction,
        thread_id: str,
        new_name: str
    ):
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("このコマンドを使用する権限がありません。", ephemeral=True)
            return

        try:
            thread_id = int(thread_id)
            thread = await self.bot.fetch_channel(thread_id)
            
            if not thread or not isinstance(thread, discord.Thread):
                await interaction.response.send_message("無効なスレッドIDです。", ephemeral=True)
                return
                
            # スレッドの作成者を確認
            thread_owner = await self.get_thread_owner(thread)
            
            if thread_owner == self.bot_id:
                await thread.edit(name=new_name)
                await interaction.response.send_message(f"スレッド名を「{new_name}」に変更しました。")
            else:
                await interaction.response.send_message("そのスレッドIDはBotが作成したものではありません、IDを確認してください。", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("無効なスレッドIDです。数値を入力してください。", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)

    async def get_thread_owner(self, thread: discord.Thread) -> Optional[int]:
        """スレッドの作成者のIDを取得する"""
        try:
            # スレッドの最初のメッセージを取得
            async for message in thread.history(limit=1, oldest_first=True):
                return message.author.id
        except:
            pass
            
        # 最初のメッセージが取得できない場合はNoneを返す
        return None

async def setup(bot):
    await bot.add_cog(Archive(bot))
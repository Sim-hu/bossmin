import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Dict, Optional

class KeepMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sticky_messages: Dict[int, Dict[int, int]] = {}
        self.message_contents: Dict[int, str] = {}
        self.load_sticky_messages()

    def load_sticky_messages(self):
        """設定ファイルから固定メッセージの情報を読み込む"""
        # dataディレクトリが存在しない場合は作成
        if not os.path.exists('data'):
            os.makedirs('data')
        
        # 設定ファイルのパス
        file_path = 'data/sticky_messages.json'
        
        # ファイルが存在しない場合は空のJSONを作成
        if not os.path.exists(file_path):
            default_data = {
                'contents': {}
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=4)
        
        # 設定を読み込み
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.message_contents = data.get('contents', {})
                # 文字列のキーを整数に変換
                self.message_contents = {int(k): v for k, v in self.message_contents.items()}
        except (json.JSONDecodeError, FileNotFoundError):
            # JSONの解析エラーが発生した場合も空の辞書で初期化
            self.message_contents = {}

    def save_sticky_messages(self):
        """固定メッセージの情報を設定ファイルに保存"""
        data = {
            'contents': self.message_contents
        }
        with open('data/sticky_messages.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    async def set_sticky_message(self, channel_id: int, content: str) -> Optional[discord.Message]:
        """チャンネルに固定メッセージを設定する"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return None

        # 既存の固定メッセージを削除
        if channel_id in self.sticky_messages:
            for old_message_id in self.sticky_messages[channel_id].values():
                try:
                    old_message = await channel.fetch_message(old_message_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

        # 新しい固定メッセージを送信
        new_message = await channel.send(content)
        self.sticky_messages[channel_id] = {new_message.id: new_message.id}
        self.message_contents[channel_id] = content
        self.save_sticky_messages()
        
        return new_message

    async def remove_sticky_message(self, channel_id: int) -> bool:
        """チャンネルから固定メッセージを削除"""
        if channel_id not in self.sticky_messages:
            return False

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return False

        # メッセージを削除
        for message_id in self.sticky_messages[channel_id].values():
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        # データを削除
        del self.sticky_messages[channel_id]
        if channel_id in self.message_contents:
            del self.message_contents[channel_id]
        self.save_sticky_messages()
        
        return True

    def is_admin(self, member: discord.Member) -> bool:
        """メンバーが管理者権限を持っているかチェック"""
        return member.guild_permissions.administrator

    class StickyModal(discord.ui.Modal, title='固定メッセージの設定'):
        # 改行可能な大きいテキストフィールド
        message = discord.ui.TextInput(
            label='固定メッセージの内容',
            style=discord.TextStyle.paragraph,
            placeholder='ここに固定したいメッセージを入力してください。\n改行も可能です。',
            max_length=2000,
            required=True
        )

        async def on_submit(self, interaction: discord.Interaction):
            cog = interaction.client.get_cog('KeepMessage')
            channel = self.channel
            await cog.set_sticky_message(channel.id, str(self.message))
            await interaction.response.send_message(
                f"{channel.mention} に固定メッセージを設定しました。",
                ephemeral=True
            )

    @app_commands.command(name="sticky", description="指定したチャンネルにメッセージを固定します")
    @app_commands.describe(
        channel="メッセージを固定するチャンネル（指定がない場合は現在のチャンネル）"
    )
    async def sticky_slash(
        self, 
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """
        スラッシュコマンドで固定メッセージを設定
        """
        # 管理者権限チェック
        if not self.is_admin(interaction.user):
            await interaction.response.send_message("このコマンドは管理者のみ使用できます。", ephemeral=True)
            return

        # モーダルを表示
        modal = self.StickyModal()
        modal.channel = channel or interaction.channel
        await interaction.response.send_modal(modal)

    @app_commands.command(name="unsticky", description="固定メッセージを解除します")
    @app_commands.describe(
        channel="固定メッセージを解除するチャンネル（指定がない場合は現在のチャンネル）"
    )
    async def unsticky_slash(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """
        スラッシュコマンドで固定メッセージを解除
        """
        # 管理者権限チェック
        if not self.is_admin(interaction.user):
            await interaction.response.send_message("このコマンドは管理者のみ使用できます。", ephemeral=True)
            return

        target_channel = channel or interaction.channel
        
        if await self.remove_sticky_message(target_channel.id):
            await interaction.response.send_message(
                f"{target_channel.mention} の固定メッセージを解除しました。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{target_channel.mention} には固定メッセージが設定されていません。",
                ephemeral=True
            )

    @app_commands.command(name="liststicky", description="全ての固定メッセージを表示します")
    async def list_sticky_slash(self, interaction: discord.Interaction):
        """
        スラッシュコマンドで固定メッセージの一覧を表示
        """
        # 管理者権限チェック
        if not self.is_admin(interaction.user):
            await interaction.response.send_message("このコマンドは管理者のみ使用できます。", ephemeral=True)
            return

        if not self.message_contents:
            await interaction.response.send_message("固定メッセージは設定されていません。", ephemeral=True)
            return

        embed = discord.Embed(title="固定メッセージ一覧", color=discord.Color.blue())
        
        for channel_id, content in self.message_contents.items():
            channel = self.bot.get_channel(channel_id)
            if channel:
                # メッセージが長い場合は省略
                short_content = content[:1000] + "..." if len(content) > 1000 else content
                embed.add_field(
                    name=f"#{channel.name}",
                    value=short_content,
                    inline=False
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        """新しいメッセージが送信されたときに固定メッセージを更新"""
        if message.author.bot:
            return
            
        channel_id = message.channel.id
        
        # チャンネルに固定メッセージが設定されていない場合は無視
        if channel_id not in self.message_contents:
            return

        # 固定メッセージ自体は無視
        if channel_id in self.sticky_messages and message.id in self.sticky_messages[channel_id]:
            return

        content = self.message_contents[channel_id]
        await self.set_sticky_message(channel_id, content)

async def setup(bot):
    await bot.add_cog(KeepMessage(bot))
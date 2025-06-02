from discord import app_commands
import discord
from discord.ext import commands
import logging
from typing import Optional, List

class NoPrivateMessageCheck:
    """DMでのコマンド使用を禁止するカスタムチェック"""
    async def check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                "⚠️ このコマンドはDMでは使用できません。サーバー内で使用してください。",
                ephemeral=True
            )
            return False
        return True

def no_dm():
    """DMでのコマンド使用を禁止するデコレータ"""
    async def predicate(interaction: discord.Interaction) -> bool:
        return await NoPrivateMessageCheck().check(interaction)
    return app_commands.check(predicate)

class BaseCog(commands.Cog):
    """全てのCogの基底クラス"""
    def __init__(self, bot: commands.Bot):
        commands.Cog.__init__(self)  # 正しい初期化を追加
        self.bot = bot
        self.logger = logging.getLogger(f'bot.{self.__class__.__name__.lower()}')
        # コマンドにDMチェックを追加
        for cmd in self.get_app_commands():
            cmd.add_check(NoPrivateMessageCheck().check)

    def get_app_commands(self) -> List[app_commands.Command]:
        """アプリケーションコマンドを取得"""
        return [
            cmd for cmd in self.__cog_app_commands__
            if isinstance(cmd, app_commands.Command)
        ]

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """グローバルなエラーハンドラー"""
        try:
            if isinstance(error, app_commands.CheckFailure):
                # DMチェックの失敗は既にメッセージが送信されているため、ここでは何もしない
                return
            
            elif isinstance(error, app_commands.CommandOnCooldown):
                await self.handle_error_response(
                    interaction,
                    f"⚠️ このコマンドは現在クールダウン中です。{error.retry_after:.2f}秒後に再試行してください。"
                )
                
            elif isinstance(error, app_commands.MissingPermissions):
                await self.handle_error_response(
                    interaction,
                    f"⚠️ このコマンドを実行するには以下の権限が必要です：{', '.join(error.missing_permissions)}"
                )
                
            elif isinstance(error, app_commands.BotMissingPermissions):
                await self.handle_error_response(
                    interaction,
                    f"⚠️ Botに必要な権限がありません：{', '.join(error.missing_permissions)}"
                )
                
            else:
                await self.handle_error_response(
                    interaction,
                    "❌ 内部エラーが発生しました。管理者に連絡してください。",
                    error
                )
                
        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))

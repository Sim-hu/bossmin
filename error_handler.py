import discord
from discord import app_commands
from discord.ext import commands
import logging
import traceback
from typing import Optional

class ErrorHandler(commands.Cog):
    """エラーハンドリングを行うCog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.error_handler')

    async def handle_error_response(self, interaction: discord.Interaction, 
                                  error_message: str, 
                                  error: Optional[Exception] = None, 
                                  ephemeral: bool = True):
        """エラーレスポンスを送信し、ログに記録する"""
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=ephemeral)
            else:
                await interaction.followup.send(error_message, ephemeral=ephemeral)
                
            if error:
                self.logger.error(
                    f"Error in {interaction.command.name}: {str(error)}\n"
                    f"{''.join(traceback.format_exception(type(error), error, error.__traceback__))}"
                )
        except Exception as e:
            self.logger.error(f"Failed to send error response: {e}")

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

async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
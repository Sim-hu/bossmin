import discord
from discord.ext import commands, tasks
import psutil
import platform
import datetime
import asyncio
import os
from typing import Optional
from utils.checks import BaseCog, NoPrivateMessageCheck
from discord import app_commands

class StatsManager(BaseCog):
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)  # BaseCogの__init__を正しく呼び出す
        self._is_running = True
        self.update_stats.start()

    def owner_only():
        async def predicate(interaction: discord.Interaction) -> bool:
            owner_id = int(os.getenv('OWNER_ID', '589736597935620097'))
            if interaction.user.id != owner_id:
                await interaction.response.send_message(
                    "⚠️ このコマンドはBotのオーナーのみが使用できます。",
                    ephemeral=True
                )
                return False
            return True
        return app_commands.check(predicate)

    def cog_unload(self):
        self._is_running = False
        self.update_stats.cancel()

    async def get_cpu_percent(self) -> float:
        """CPU使用率を非同期的に取得"""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, psutil.cpu_percent, 0.1)
        except Exception as e:
            self.logger.error(f"Error getting CPU percent: {e}")
            return 0.0

    @tasks.loop(minutes=5)
    async def update_stats(self):
        """5分ごとにボットの統計情報を更新"""
        if not self._is_running:
            self.update_stats.cancel()
            return

        try:
            # CPU使用率を非同期的に取得
            cpu_percent = await self.get_cpu_percent()
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            # 接続しているサーバー数
            guild_count = len(self.bot.guilds)
            
            # ステータスメッセージを更新
            status = f'CPU: {cpu_percent}% | Servers: {guild_count}'
            
            if self._is_running:  # 状態更新前に再度チェック
                await self.bot.change_presence(activity=discord.Game(name=status))
            
            self.logger.info(f"Stats updated - {status}")
        
        except asyncio.CancelledError:
            self.logger.info("Stats update cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error updating stats: {e}")

    @update_stats.before_loop
    async def before_update_stats(self):
        """ボットが準備完了するまで待機"""
        await self.bot.wait_until_ready()

    @update_stats.error
    async def update_stats_error(self, error):
        """統計更新のエラーハンドラー"""
        if isinstance(error, asyncio.CancelledError):
            self.logger.info("Stats update task cancelled")
        else:
            self.logger.error(f"Unexpected error in stats update: {error}")

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsManager(bot))
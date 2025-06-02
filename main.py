import discord
import asyncio
import logging  
import traceback
import sys
from datetime import datetime
import json
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
from database import Database
from utils.checks import BaseCog
from utils.config_manager import ConfigManager

load_dotenv()

class AdminBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.guild_messages = True
        
        super().__init__(
            command_prefix="^",  
            intents=discord.Intents.all(),
            help_command=None
        )
        self.config = {
            'spam_settings': {
                'message_count': 5,
                'time_window': 5,
                'action': 'timeout',
                'timeout_duration': 300
            }
        }
        self.config_manager = ConfigManager()

        # ロギング設定（既存のまま）
        os.makedirs('logs', exist_ok=True)
        self.debug_mode = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
        
        log_filename = f'logs/debug_{datetime.now().strftime("%Y%m%d")}.log'
        logging_level = logging.DEBUG if self.debug_mode else logging.INFO
        
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        file_handler.setLevel(logging_level)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        
        logging.basicConfig(
            level=logging_level,
            handlers=[file_handler, console_handler]
        )
        
        logging.getLogger('discord').setLevel(logging.ERROR)
        logging.getLogger('discord.http').setLevel(logging.ERROR)
        logging.getLogger('discord.state').setLevel(logging.ERROR)
        logging.getLogger('discord.gateway').setLevel(logging.ERROR)
        
        self.logger = logging.getLogger('bot')
        self.logger.setLevel(logging_level)

        try:
            self.db = Database()
            self.config_manager = ConfigManager()
        except Exception as e:
            self.logger.error(f"Failed to initialize core components: {e}")
            raise

    async def setup_hook(self):
        global_config = self.config_manager.get_global_config()
        self.config.update(global_config)

        initial_extensions = [
            'error_handler',
            'cogs.admin',
            'cogs.logging',
            'cogs.stats',
            'cogs.keepmessage',
            'cogs.archive',
            'cogs.anti_spam',
            'cogs.mod',
            'cogs.debug'
        ]
    
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                print(f"Failed to load extension {extension}:", file=sys.stderr)
                traceback.print_exc()
    
        try:
            self.logger.info("Syncing commands globally...")
            await self.tree.sync()
            self.logger.info("Commands synced successfully!")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")
            traceback.print_exc()

    async def close(self):
        """Botのシャットダウン時の処理"""
        try:
            self.logger.info("Bot is shutting down gracefully...")
            if hasattr(self, 'db') and self.db is not None:
                try:
                    await self.db.close()
                except Exception as e:
                    self.logger.error(f"Error closing database: {e}")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            try:
                await super().close()
            except Exception as e:
                self.logger.error(f"Error in parent close: {e}")
        
    async def on_ready(self):
        self.logger.info(f'Logged in as {self.user.name}')
        
        status_message = os.getenv('STATUS_MESSAGE', '監視中')
        activity = discord.Game(name=status_message)
        
        try:
            await self.change_presence(activity=activity)
            self.logger.info(f"Status set to: {status_message}")
        except Exception as e:
            self.logger.error(f"Failed to set status: {str(e)}")

    async def on_error(self, event, *args, **kwargs):
        error_msg = traceback.format_exc()
        self.logger.error(f"Error in {event}:\n{error_msg}")
        
        if self.debug_mode:
            error_channel_id = os.getenv('ERROR_LOG_CHANNEL')
            if error_channel_id:
                try:
                    channel = self.get_channel(int(error_channel_id))
                    if channel:
                        await channel.send(
                            embed=discord.Embed(
                                title="エラーが発生しました",
                                description=f"Event: {event}\n```py\n{error_msg[:1900]}```",
                                color=discord.Color.red(),
                                timestamp=datetime.now()
                            )
                        )
                except Exception as e:
                    self.logger.error(f"Failed to send error message: {e}")

async def main():
    try:
        logging.getLogger('discord').setLevel(logging.ERROR)
        logging.getLogger('asyncio').setLevel(logging.ERROR)
        logging.getLogger('websockets').setLevel(logging.ERROR)
        logging.getLogger('charset_normalizer').setLevel(logging.ERROR)
        
        bot = AdminBot()
        try:
            async with bot:
                await bot.start(os.getenv('DISCORD_TOKEN'))
        except (KeyboardInterrupt, SystemExit):
            logging.info("Received shutdown signal...")  # self.loggerではなくloggingを使用
        except discord.errors.HTTPException as e:
            if e.status == 429:  # レート制限エラー
                logging.error("Rate limit exceeded. Waiting before reconnecting...")
                await asyncio.sleep(60)  # 1分待機
            else:
                raise
        finally:
            if not bot.is_closed():
                await bot.close()
    except Exception as e:
        logging.error(f"Critical error in main: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
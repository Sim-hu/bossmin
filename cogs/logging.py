import discord
from discord.ext import commands
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional

from admin.message_logging import MessageLogging
from admin.member_logging import MemberLogging
from admin.server_logging import ServerLogging
from admin.voice_logging import VoiceLogging
from admin.thread_logging import ThreadLogging

class LoggingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.logging')
        self.config_manager = bot.config_manager
        self.log_channels = {}
        self.vc_log_channels = {}
        self.archive_channel = None
        self.load_config()
        
        # 各種ログ機能のインスタンスを作成
        self.message_logging = MessageLogging(self)
        self.member_logging = MemberLogging(self)
        self.server_logging = ServerLogging(self)
        self.voice_logging = VoiceLogging(self)
        self.thread_logging = ThreadLogging(self)

    def load_config(self):
        """設定を読み込む"""
        try:
            global_config = self.config_manager.get_global_config()
            
            # log_channels の設定を読み込む
            self.log_channels = global_config.get('log_channels', {})
            
            # vc_log_channels の設定を読み込む
            self.vc_log_channels = global_config.get('vc_log_channels', {})
            
            # アーカイブチャンネルの設定を読み込む
            archive_channel_id = self.config_manager.get_archive_channel()
            if archive_channel_id:
                self.archive_channel = self.bot.get_channel(int(archive_channel_id))
                
        except Exception as e:
            self.logger.error(f"設定の読み込み中にエラーが発生しました: {e}")

    def get_archive_channel(self) -> Optional[discord.TextChannel]:
        """アーカイブチャンネルを取得する"""
        try:
            # ConfigManagerから直接チャンネルIDを取得
            channel_id = self.config_manager.get_archive_channel()
            if channel_id:
                # チャンネルIDをintに変換してからチャンネルを取得
                return self.bot.get_channel(int(channel_id))
            return None
        except Exception as e:
            self.logger.error(f"アーカイブチャンネルの取得中にエラーが発生しました: {e}")
            return None

    async def set_archive_channel(self, channel_id: int) -> bool:
        """アーカイブチャンネルを設定する"""
        try:
            # ConfigManagerを使用してチャンネルIDを保存
            success = self.config_manager.set_archive_channel(channel_id)
            if success:
                # 設定が成功したら、現在のインスタンスのarchive_channelも更新
                self.archive_channel = self.bot.get_channel(channel_id)
            return success
        except Exception as e:
            self.logger.error(f"アーカイブチャンネルの設定中にエラーが発生しました: {e}")
            return False

    async def send_log(self, guild_id: int, embed: discord.Embed, log_type: str = 'general') -> bool:
        """
        ログを適切なチャンネルに送信する

        Parameters:
        -----------
        guild_id : int
            ギルドID
        embed : discord.Embed
            送信するEmbed
        log_type : str
            'general' または 'vc' でログタイプを指定
            
        Returns:
        --------
        bool
            送信成功時はTrue、失敗時はFalse
        """
        import asyncio
        max_retries = 3
        base_delay = 1.0

        # VCログかどうかを判断
        if isinstance(embed.title, str) and ("VC参加" in embed.title or "VC退出" in embed.title):
            log_type = 'vc'

        # チャンネルの取得
        target_channel = await self.get_log_channel(guild_id, log_type)
        if not target_channel:
            self.logger.warning(f"ログチャンネルが見つかりません（ギルド: {guild_id}）")
            return False

        # レート制限を考慮した送信処理
        for attempt in range(max_retries):
            try:
                await target_channel.send(embed=embed)
                return True
            except discord.HTTPException as e:
                if e.status == 429:  # レート制限エラー
                    if attempt == max_retries - 1:
                        self.logger.error(f"レート制限によりログの送信に失敗しました: {e}")
                        return False

                    retry_after = e.retry_after if hasattr(e, 'retry_after') else base_delay * (attempt + 1)
                    self.logger.warning(f"レート制限中です。{retry_after}秒後に再試行します (試行 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_after)
                else:
                    self.logger.error(f"ログ送信中にエラーが発生しました: {e}")
                    return False
        
        return False

    async def get_log_channel(self, guild_id: int, log_type: str = 'general') -> Optional[discord.TextChannel]:
        """
        指定されたギルドとログタイプに対応するログチャンネルを取得
        VCログの場合、専用チャンネルが未設定なら一般ログチャンネルにフォールバック
        
        Parameters:
        -----------
        guild_id : int
            ギルドID
        log_type : str
            'general' または 'vc' でログタイプを指定
            
        Returns:
        --------
        Optional[discord.TextChannel]
            ログチャンネル。設定がない場合はNone
        """
        try:
            guild_config = self.config_manager.get_guild_config(str(guild_id))
            if not guild_config:
                return None
            
            channel_id = None
            if log_type == 'vc':
                # まずVCログチャンネルを試す
                channel_id = guild_config.get('vc_log_channel')
                # VCログチャンネルが未設定の場合、一般ログチャンネルを試す
                if not channel_id:
                    channel_id = guild_config.get('log_channel')
            else:
                channel_id = guild_config.get('log_channel')
            
            if channel_id:
                return self.bot.get_channel(int(channel_id))
        except Exception as e:
            self.logger.error(f"ログチャンネルの取得中にエラーが発生しました: {e}")
        return None

    # 各種イベントリスナーを対応するクラスに委譲
    @commands.Cog.listener()
    async def on_message(self, message):
        await self.message_logging.on_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        await self.message_logging.on_message_edit(before, after)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        await self.message_logging.on_message_delete(message)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        await self.message_logging.on_bulk_message_delete(messages)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self.member_logging.on_member_update(before, after)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.member_logging.on_member_join(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.member_logging.on_member_remove(member)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.member_logging.on_member_ban(guild, user)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.member_logging.on_member_unban(guild, user)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.server_logging.on_guild_channel_create(channel)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.server_logging.on_guild_channel_delete(channel)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        await self.server_logging.on_guild_channel_update(before, after)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        await self.server_logging.on_guild_update(before, after)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        await self.server_logging.on_guild_emojis_update(guild, before, after)

    @commands.Cog.listener()
    async def on_guild_stickers_update(self, guild, before, after):
        await self.server_logging.on_guild_stickers_update(guild, before, after)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        await self.server_logging.on_guild_role_update(before, after)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild):
        await self.server_logging.on_guild_integrations_update(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        await self.server_logging.on_invite_create(invite)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        await self.voice_logging.on_voice_state_update(member, before, after)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await self.thread_logging.on_thread_create(thread)

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):
        await self.thread_logging.on_thread_update(before, after)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        await self.thread_logging.on_thread_delete(thread)

    @commands.Cog.listener()
    async def on_raw_thread_update(self, payload):
        await self.thread_logging.on_raw_thread_update(payload)

async def setup(bot: commands.Bot):
    # シグナルハンドラの設定
    def signal_handler(sig, frame):
        print("\nBot is shutting down gracefully...")
        # 必要なクリーンアップ処理をここに追加
        sys.exit(0)
    
    # SIGINT (Ctrl+C) とSIGTERM のハンドラを設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await bot.add_cog(LoggingCog(bot))

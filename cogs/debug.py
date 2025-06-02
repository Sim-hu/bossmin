import discord
from discord import app_commands
from discord.ext import commands
import psutil
import platform
import sys
import os
import io
from datetime import datetime
import logging
import threading
from typing import Optional
from pathlib import Path
import asyncio
import traceback
from discord.ext.commands import Context
from utils.checks import BaseCog
from utils import ConfigManager

class DebugManager(BaseCog, commands.GroupCog, name="debug"):
    """デバッグ関連のコマンドを管理するCog"""
    
    def __init__(self, bot: commands.Bot):
        BaseCog.__init__(self, bot)  # BaseCogの初期化
        commands.GroupCog.__init__(self)  # GroupCogの初期化
        self.config = ConfigManager()
        self.config_manager = self.config

        self._last_result = None
        if not hasattr(bot, 'start_time'):
            bot.start_time = datetime.now()
        
        # 環境変数から設定を読み込む
        self.OWNER_ID = int(os.getenv('OWNER_ID', '589736597935620097'))
        self.ERROR_LOG_CHANNEL = int(os.getenv('ERROR_LOG_CHANNEL', '1301980678287523991'))
        self.DEBUG_MODE = os.getenv('DEBUG_MODE', 'True').lower() == 'true'

    async def is_owner(self, interaction: discord.Interaction) -> bool:
        """ユーザーがオーナーかどうかをチェック"""
        return interaction.user.id == self.OWNER_ID

    def owner_only():
        """オーナー専用コマンドのデコレータ"""
        async def predicate(interaction: discord.Interaction) -> bool:
            if not interaction.guild:
                return False
            cog = interaction.client.get_cog('debug')
            if not cog:
                return False
            is_owner = await cog.is_owner(interaction)
            if not is_owner:
                # 不正使用のログを記録
                await cog.log_unauthorized_access(interaction)
            return is_owner
        return app_commands.check(predicate)

    async def log_unauthorized_access(self, interaction: discord.Interaction):
        """不正なアクセス試行をログチャンネルに記録"""
        try:
            channel = self.bot.get_channel(self.ERROR_LOG_CHANNEL)
            if channel:
                embed = discord.Embed(
                    title="Unauthorized Debug Command Access",
                    color=discord.Color.yellow(),
                    timestamp=datetime.now()
                )
                embed.add_field(
                    name="User Information",
                    value=f"Name: {interaction.user} ({interaction.user.id})\n"
                          f"Created: {interaction.user.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    inline=False
                )
                embed.add_field(
                    name="Server Information",
                    value=f"Name: {interaction.guild.name} ({interaction.guild.id})\n"
                          f"Owner: {interaction.guild.owner} ({interaction.guild.owner_id})",
                    inline=False
                )
                embed.add_field(
                    name="Command Information",
                    value=f"Command: {interaction.command.name}\n"
                          f"Full Command: {interaction.command.qualified_name}\n"
                          f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    inline=False
                )
                
                await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to log unauthorized access: {e}")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Cogレベルのエラーハンドラー"""
        try:
            if isinstance(error, app_commands.CheckFailure):
                # オーナー権限チェックの失敗は通常のエラーとして扱わない
                await self.send_response(
                    interaction,
                    "⚠️ このコマンドはBotのオーナーのみが使用できます。",
                    ephemeral=True
                )
                return

            # エラー情報の記録（CheckFailure以外）
            error_msg = str(error)
            tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            self.logger.error(f"Debug command error in {interaction.command.name}:\n{tb}")
            
            # DMでの使用をチェック
            if not interaction.guild:
                await self.send_response(
                    interaction,
                    "⚠️ デバッグコマンドはDMでは使用できません。"
                )
                return

            # その他のエラーの処理
            if isinstance(error, app_commands.MissingPermissions):
                await self.send_response(
                    interaction,
                    f"⚠️ このコマンドを実行するには以下の権限が必要です：{', '.join(error.missing_permissions)}"
                )
            elif isinstance(error, (app_commands.CommandOnCooldown, app_commands.CommandLimitReached)):
                await self.send_response(
                    interaction,
                    f"⚠️ {error_msg}"
                )
            else:
                # 予期せぬエラーの処理
                if self.DEBUG_MODE:
                    await self.send_response(
                        interaction,
                        f"❌ エラーが発生しました：```py\n{tb[:1900]}```"
                    )
                else:
                    await self.send_response(
                        interaction,
                        "❌ 内部エラーが発生しました。管理者に連絡してください。"
                    )

            # エラーログの送信（CheckFailure以外）
            await self.send_error_log(tb, interaction)

        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")
            
    def _create_guild_info_embed_implementation(self, guild, member_status, channels):
        embed = discord.Embed(
            title=f"Guild Information - {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Basic guild info
        embed.add_field(
            name="Basic Info",
            value=f"```\n"
                  f"ID: {guild.id}\n"
                  f"Owner: {guild.owner}\n"
                  f"Region: {guild.region if hasattr(guild, 'region') else 'Unknown'}\n"
                  f"Created: {guild.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                  f"Verification Level: {guild.verification_level}\n"
                  f"```",
            inline=False
        )
        
        # Member stats
        embed.add_field(
            name="Member Stats",
            value=f"```\n"
                  f"Total: {guild.member_count}\n"
                  f"Online: {member_status['online']}\n"
                  f"Idle: {member_status['idle']}\n"
                  f"DND: {member_status['dnd']}\n"
                  f"Offline: {member_status['offline']}\n"
                  f"```",
            inline=True
        )
        
        # Channel stats
        embed.add_field(
            name="Channel Stats",
            value=f"```\n"
                  f"Text: {channels['text']}\n"
                  f"Voice: {channels['voice']}\n"
                  f"Categories: {channels['categories']}\n"
                  f"Total: {channels['total']}\n"
                  f"```",
            inline=True
        )
        
        return embed

    def _get_voice_channel_info_implementation(self, vc):
        members = len(vc.members)
        user_list = "\n".join(f"- {m.name}" for m in vc.members) if members > 0 else "No users"
        return f"Users: {members}\nBitrate: {vc.bitrate//1000}kbps\n{user_list}"

    async def _read_log_file_implementation(self, lines: int) -> Optional[str]:
        try:
            log_file = "bot.log"
            if not os.path.exists(log_file):
                return None
            
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.readlines()
                return ''.join(content[-lines:])
        except Exception as e:
            self.logger.error(f"Error reading log file: {e}")
            return None

    def _add_basic_info_to_embed_implementation(self, embed):
        uptime = datetime.now() - self.bot.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed.add_field(
            name="Basic Info",
            value=f"```\n"
                  f"Uptime: {hours}h {minutes}m {seconds}s\n"
                  f"Latency: {round(self.bot.latency * 1000)}ms\n"
                  f"Version: {discord.__version__}\n"
                  f"```",
            inline=False
        )

    def _add_stats_info_to_embed_implementation(self, embed):
        embed.add_field(
            name="Stats",
            value=f"```\n"
                  f"Guilds: {len(self.bot.guilds)}\n"
                  f"Users: {len(self.bot.users)}\n"
                  f"Commands: {len(self.bot.tree.get_commands())}\n"
                  f"```",
            inline=True
        )

    def _add_system_info_to_embed_implementation(self, embed):
        process = psutil.Process()
        embed.add_field(
            name="System",
            value=f"```\n"
                  f"CPU: {psutil.cpu_percent()}%\n"
                  f"RAM: {process.memory_info().rss / 1024 / 1024:.2f} MB\n"
                  f"Threads: {len(threading.enumerate())}\n"
                  f"```",
            inline=True
        )

    async def send_error_log(self, error_info: str, interaction: discord.Interaction):
        """エラーログチャンネルにエラー情報を送信する"""
        try:
            channel = self.bot.get_channel(self.ERROR_LOG_CHANNEL)
            if channel:
                embed = discord.Embed(
                    title="Debug Command Error",
                    description=f"Command: {interaction.command.name}\n"
                              f"User: {interaction.user} (ID: {interaction.user.id})\n"
                              f"Guild: {interaction.guild.name} (ID: {interaction.guild.id})\n"
                              f"Error: ```py\n{error_info[:1900]}```",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to send error to log channel: {e}")

    async def send_response(self, interaction: discord.Interaction, content: str, ephemeral: bool = True):
        """インタラクションの状態に応じて適切な方法でメッセージを送信する"""
        try:
            if interaction.response.is_done():
                if hasattr(interaction, "followup"):
                    await interaction.followup.send(content, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(content, ephemeral=ephemeral)
        except Exception as e:
            self.logger.error(f"Error sending response: {e}")

    def get_archive_channel(self):
        """アーカイブチャンネルのIDを取得します"""
        try:
            config = self.config.get_global_config()
            return config.get('photo_archive_channel')
        except Exception as e:
            self.logger.error(f"Error getting archive channel: {e}")
            return None        

    @app_commands.command(name="info")
    @owner_only()
    @app_commands.describe(target="表示する情報の種類 (all/system/memory/cache/temp)")
    async def display_info(self, interaction: discord.Interaction, target: str = "all"):
        """デバッグ情報を表示します"""
        try:
            valid_targets = ["all", "system", "memory", "cache", "temp"]
            if target not in valid_targets:
                await interaction.response.send_message(
                    f"❌ Invalid target. Available targets: {', '.join(valid_targets)}",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="Debug Information",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if target in ["all", "system"]:
                embed.add_field(
                    name="System Info",
                    value=f"```\n"
                          f"OS: {platform.system()} {platform.version()}\n"
                          f"Python: {platform.python_version()}\n"
                          f"Discord.py: {discord.__version__}\n"
                          f"Process ID: {os.getpid()}\n"
                          f"```",
                    inline=False
                )

            if target in ["all", "memory"]:
                process = psutil.Process()
                memory_info = process.memory_info()
                embed.add_field(
                    name="Memory Usage",
                    value=f"```\n"
                          f"RSS: {memory_info.rss / 1024 / 1024:.2f} MB\n"
                          f"VMS: {memory_info.vms / 1024 / 1024:.2f} MB\n"
                          f"System Memory: {psutil.virtual_memory().percent}%\n"
                          f"```",
                    inline=False
                )

            if target in ["all", "cache"]:
                embed.add_field(
                    name="Cache Info",
                    value=f"```\n"
                          f"Guilds Cached: {len(self.bot.guilds)}\n"
                          f"Users Cached: {len(self.bot.users)}\n"
                          f"Messages Cached: {sum(len(c._state._messages) for c in self.bot.get_all_channels() if isinstance(c, discord.TextChannel))}\n"
                          f"```",
                    inline=False
                )

            if target in ["all", "temp"]:
                cpu_usage = psutil.cpu_percent(interval=1)
                embed.add_field(
                    name="Runtime Info",
                    value=f"```\n"
                          f"Latency: {round(self.bot.latency * 1000)}ms\n"
                          f"CPU Usage: {cpu_usage}%\n"
                          f"Thread Count: {len(threading.enumerate())}\n"
                          f"```",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            self.logger.error(f"Error in display_info command: {str(e)}")
            await interaction.response.send_message(
                "❌ コマンドの実行中にエラーが発生しました。",
                ephemeral=True
            )

    @app_commands.command(name="photo")
    @app_commands.default_permissions(administrator=True)
    async def setup_photo_archive(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        画像アーカイブチャンネルを設定します。
        
        Parameters
        ----------
        channel : discord.TextChannel
            アーカイブ先のチャンネル
        """
        try:
            # チャンネルの権限チェック
            bot_member = interaction.guild.get_member(self.bot.user.id)
            required_permissions = [
                "view_channel",
                "send_messages",
                "embed_links",
                "attach_files"
            ]
            
            missing_perms = []
            channel_perms = channel.permissions_for(bot_member)
            for perm in required_permissions:
                if not getattr(channel_perms, perm, False):
                    missing_perms.append(perm)
            
            if missing_perms:
                perms_text = ", ".join(missing_perms)
                await interaction.response.send_message(
                    f"❌ ボットに必要な権限がありません: {perms_text}",
                    ephemeral=True
                )
                return
    
            # グローバル設定として保存
            success = self.config.update_global_config({
                'photo_archive_channel': channel.id
            })
    
            if success:
                # テスト用の埋め込みを送信
                test_embed = discord.Embed(
                    title="画像アーカイブテスト",
                    description="これはテストメッセージです。",
                    color=discord.Color.blue()
                )
                try:
                    await channel.send(embed=test_embed)
                    await interaction.response.send_message(
                        f"✅ グローバルアーカイブチャンネルを {channel.mention} に設定しました。\n"
                        "テストメッセージの送信に成功しました。",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"⚠️ チャンネルは設定されましたが、テストメッセージの送信に失敗しました: {str(e)}",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ 設定の保存に失敗しました。",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error in setup_photo_archive: {e}")
            await interaction.response.send_message(
                f"❌ エラーが発生しました: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="check_photo")
    @app_commands.default_permissions(administrator=True)
    async def check_photo_archive(self, interaction: discord.Interaction):
        """現在の画像アーカイブの設定を確認します。"""
        try:
            # グローバル設定から取得
            channel_id = self.get_archive_channel()
            
            if not channel_id:
                await interaction.response.send_message(
                    "❌ グローバルアーカイブチャンネルが設定されていません。",
                    ephemeral=True
                )
                return
                
            channel = self.bot.get_channel(channel_id)
            
            if channel:
                await interaction.response.send_message(
                    f"✅ 現在のグローバルアーカイブチャンネル: {channel.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "⚠️ 設定されたチャンネルが見つかりません。",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error in check_photo_archive: {e}")
            await interaction.response.send_message(
                f"❌ エラーが発生しました: {str(e)}",
                ephemeral=True
            )
            
    @app_commands.command(name="guild")
    @owner_only()
    @app_commands.describe(guild_id="サーバーID（省略時は現在のサーバー）")
    async def display_guild(self, interaction: discord.Interaction, guild_id: Optional[str] = None):
        """指定したサーバーの詳細情報を表示します"""
        try:
            # guild_idが文字列として渡された場合に整数に変換
            target_guild_id = int(guild_id) if guild_id else interaction.guild.id
            guild = self.bot.get_guild(target_guild_id)
            
            if not guild:
                await interaction.response.send_message(
                    "❌ 指定されたサーバーが見つかりません。",
                    ephemeral=True
                )
                return

            member_status = {
                "online": sum(1 for m in guild.members if m.status == discord.Status.online),
                "idle": sum(1 for m in guild.members if m.status == discord.Status.idle),
                "dnd": sum(1 for m in guild.members if m.status == discord.Status.dnd),
                "offline": sum(1 for m in guild.members if m.status == discord.Status.offline)
            }

            channels = {
                "text": len(guild.text_channels),
                "voice": len(guild.voice_channels),
                "categories": len(guild.categories),
                "total": len(guild.channels)
            }

            embed = self._create_guild_info_embed_implementation(guild, member_status, channels)
            await interaction.response.send_message(embed=embed)
            
        except ValueError:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ 無効なサーバーIDです。数値を入力してください。",
                    ephemeral=True
                )
        except Exception as e:
            self.logger.error(f"Error in display_guild command: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ コマンドの実行中にエラーが発生しました。",
                    ephemeral=True
                )
            
    @app_commands.command(name="status")   
    @owner_only()  
    async def display_status(self, interaction: discord.Interaction):
        """Botの現在の状態を表示します"""
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        self._add_basic_info_to_embed_implementation(embed)
        self._add_stats_info_to_embed_implementation(embed)
        self._add_system_info_to_embed_implementation(embed)

        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="voice")   
    @owner_only()  
    @app_commands.describe(guild_id="サーバーID（省略時は現在のサーバー）")
    async def display_voice(self, interaction: discord.Interaction, guild_id: Optional[int] = None):
        """ボイスチャンネルの現在の状態を表示します"""
        guild = self.bot.get_guild(guild_id) if guild_id else interaction.guild
        if not guild:
            await interaction.response.send_message("❌ 指定されたサーバーが見つかりません。")
            return

        embed = discord.Embed(
            title=f"Voice Channel Status - {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        for vc in guild.voice_channels:
            value = self._get_voice_channel_info_implementation(vc)
            embed.add_field(
                name=f"🔊 {vc.name}",
                value=f"```\n{value}\n```",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="logs")     
    @owner_only()
    @app_commands.describe(lines="表示する行数")
    async def display_logs(self, interaction: discord.Interaction, lines: int = 10):
        """最新のログファイルの内容を表示します"""
        try:
            log_content = await self._read_log_file_implementation(lines)
            if not log_content:
                return await interaction.response.send_message("❌ No logs found.")

            chunks = [log_content[i:i+4000] for i in range(0, len(log_content), 4000)]
            await interaction.response.send_message("ログを表示します...")
            
            for i, chunk in enumerate(chunks, 1):
                embed = discord.Embed(
                    title=f"Debug Logs ({i}/{len(chunks)})",
                    description=f"```\n{chunk}\n```",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                if i == 1:
                    await interaction.edit_original_response(embed=embed)
                else:
                    await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error reading logs: {str(e)}")

    @app_commands.command(name="clear_cache") 
    @owner_only()    
    async def clear_cache(self, interaction: discord.Interaction):
        """Botのキャッシュをクリアします"""
        try:
            for channel in self.bot.get_all_channels():
                if isinstance(channel, discord.TextChannel):
                    channel._state._messages.clear()
            
            self.bot._connection._voice_clients.clear()
            
            await interaction.response.send_message("✅ キャッシュを正常にクリアしました。")
        except Exception as e:
            await interaction.response.send_message(f"❌ キャッシュのクリア中にエラーが発生しました: {str(e)}")

    @app_commands.command(name="reload_all")  
    @owner_only()   
    async def reload_all(self, interaction: discord.Interaction):
        """全ての拡張機能をリロードします"""
        success = []
        failed = []
        
        for extension in list(self.bot.extensions):
            try:
                await self.bot.reload_extension(extension)
                success.append(extension)
            except Exception as e:
                failed.append(f"{extension}: {str(e)}")
        
        embed = discord.Embed(title="Extension Reload Results", color=discord.Color.blue())
        if success:
            embed.add_field(name="✅ Reloaded", value="\n".join(success), inline=False)
        if failed:
            embed.add_field(name="❌ Failed", value="\n".join(failed), inline=False)
            
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(DebugManager(bot))
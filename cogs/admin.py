import discord
from discord.ext import commands
from discord import app_commands, Interaction, TextChannel, User, Forbidden, HTTPException
from datetime import datetime, timezone
from utils.checks import BaseCog
import logging
from typing import List, Tuple, Optional, Dict  

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

    async def delete_messages_safely(self, messages, interaction):
        """メッセージを安全に削除し、結果を返す補助メソッド"""
        deleted = 0
        old_messages = 0
        errors = 0
        
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # 14日以上経過したメッセージを分離
        recent_messages = []
        for msg in messages:
            if (now - msg.created_at).days < 14:
                recent_messages.append(msg)
            else:
                old_messages += 1
        
        # 一括削除（2以上のメッセージがある場合）
        if len(recent_messages) >= 2:
            try:
                await interaction.channel.delete_messages(recent_messages)
                deleted = len(recent_messages)
            except Exception as e:
                self.logger.error(f"Bulk delete error: {e}")
                errors = len(recent_messages)
        
        # 残りのメッセージを個別に削除
        elif len(recent_messages) == 1:
            try:
                await recent_messages[0].delete()
                deleted = 1
            except Exception as e:
                self.logger.error(f"Single delete error: {e}")
                errors = 1
        
        return deleted, old_messages, errors

    @app_commands.command(name="delete", description="指定した数のメッセージを削除")
    @app_commands.checks.has_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message("1以上の数を指定してください。", ephemeral=True)
            return
        
        logging_cog = await self.get_logging_cog()
        if not logging_cog:
            await interaction.response.send_message("LoggingCogが見つかりませんでした。", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            messages = []
            async for message in interaction.channel.history(limit=amount + 1):
                messages.append(message)
            
            # コマンドメッセージを除外
            messages = messages[1:amount + 1]
            
            if not messages:
                await interaction.followup.send("削除するメッセージが見つかりませんでした。", ephemeral=True)
                return
            
            deleted, old_messages, errors = await self.delete_messages_safely(messages, interaction)
            
            # メッセージ削除の処理が完了した後、手動でログイベントを発火
            if deleted > 0:
                # 削除に成功したメッセージのみをログに記録
                successfully_deleted = [msg for msg in messages if not (datetime.now(timezone.utc) - msg.created_at).days >= 14]
                if successfully_deleted:
                    # on_bulk_message_deleteイベントを手動で発火
                    self.bot.dispatch('bulk_message_delete', successfully_deleted)
            
            # 結果レポートの作成
            report = [f"削除試行数: {len(messages)}"]
            if deleted > 0:
                report.append(f"✅ 削除成功: {deleted}件")
            if old_messages > 0:
                report.append(f"⚠️ 14日超過のため削除不可: {old_messages}件")
            if errors > 0:
                report.append(f"❌ エラーで削除失敗: {errors}件")
                
            await interaction.followup.send("\n".join(report), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("メッセージを削除する権限がありません。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {str(e)}", ephemeral=True)
            self.logger.error(f"delete command error: {e}")
    
    async def delete_messages_safely(self, messages: List[discord.Message], interaction: discord.Interaction) -> Tuple[int, int, int]:
        """
        メッセージを安全に削除し、結果を返す
        
        Returns:
        --------
        Tuple[int, int, int]
            (削除成功数, 14日超過数, エラー数)
        """
        deleted = 0
        old_messages = 0
        errors = 0
        
        # メッセージを14日以内とそれ以外に分類
        now = datetime.now(timezone.utc)
        recent_messages = []
        
        for message in messages:
            if (now - message.created_at).days >= 14:
                old_messages += 1
                continue
            recent_messages.append(message)
        
        # 14日以内のメッセージを一括削除
        if recent_messages:
            try:
                await interaction.channel.delete_messages(recent_messages)
                deleted = len(recent_messages)
            except discord.HTTPException as e:
                self.logger.error(f"メッセージの一括削除中にエラー: {e}")
                errors = len(recent_messages)
                
        return deleted, old_messages, errors

    @app_commands.command(name="userdelete", description="指定したユーザーのメッセージを指定した数だけ削除")
    @app_commands.checks.has_permissions(administrator=True)
    async def userdelete(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            await interaction.response.send_message("1以上の数を指定してください。", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            text_channels = [ch for ch in interaction.guild.channels if isinstance(ch, discord.TextChannel)]
            total_deleted = 0
            total_old = 0
            total_errors = 0
            
            for channel in text_channels:
                if total_deleted >= amount:
                    break
                    
                try:
                    messages = []
                    async for message in channel.history(limit=None):
                        if message.author.id == user.id:
                            messages.append(message)
                            if len(messages) >= (amount - total_deleted):
                                break
                                
                    if messages:
                        deleted, old_messages, errors = await self.delete_messages_safely(messages, interaction)
                        total_deleted += deleted
                        total_old += old_messages
                        total_errors += errors
                        
                except discord.Forbidden:
                    continue
                    
            # 結果レポート
            report = [f"{user.mention} のメッセージ削除結果:"]
            report.append(f"削除試行数: {amount}")
            if total_deleted > 0:
                report.append(f"✅ 削除成功: {total_deleted}件")
            if total_old > 0:
                report.append(f"⚠️ 14日超過のため削除不可: {total_old}件")
            if total_errors > 0:
                report.append(f"❌ エラーで削除失敗: {total_errors}件")
            
            await interaction.followup.send("\n".join(report), ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"エラーが発生しました: {str(e)}", ephemeral=True)
            self.logger.error(f"userdelete command error: {e}")

    @app_commands.command(name="userdeletech", description="指定したチャンネルの指定したユーザーのメッセージを指定した数だけ削除")
    @app_commands.checks.has_permissions(administrator=True)
    async def userdeletech(self, interaction: discord.Interaction, user: discord.User, channel: discord.TextChannel, amount: int):
        if amount <= 0:
            await interaction.response.send_message("1以上の数を指定してください。", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            messages = []
            async for message in channel.history(limit=None):
                if message.author.id == user.id:
                    messages.append(message)
                    if len(messages) >= amount:
                        break
            
            if not messages:
                await interaction.followup.send(
                    f"{channel.mention} で {user.mention} のメッセージは見つかりませんでした。",
                    ephemeral=True
                )
                return
            
            deleted, old_messages, errors = await self.delete_messages_safely(messages, interaction)
            
            # 結果レポート
            report = [f"{channel.mention} での {user.mention} のメッセージ削除結果:"]
            report.append(f"削除試行数: {len(messages)}")
            if deleted > 0:
                report.append(f"✅ 削除成功: {deleted}件")
            if old_messages > 0:
                report.append(f"⚠️ 14日超過のため削除不可: {old_messages}件")
            if errors > 0:
                report.append(f"❌ エラーで削除失敗: {errors}件")
            
            await interaction.followup.send("\n".join(report), ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("メッセージを削除する権限がありません。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {str(e)}", ephemeral=True)
            self.logger.error(f"userdeletech command error: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
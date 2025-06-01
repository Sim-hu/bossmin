import discord
from datetime import datetime, timezone

class ThreadLogging:
    def __init__(self, logging_cog):
        self.logging_cog = logging_cog
        self.bot = logging_cog.bot
        self.logger = logging_cog.logger

    async def on_thread_create(self, thread):
        """スレッド作成を検知してログに記録"""
        embed = discord.Embed(title="スレッド作成", color=discord.Color.green())
        embed.add_field(name="スレッド名", value=thread.name, inline=False)
        embed.add_field(name="親チャンネル", value=thread.parent.name, inline=False)
        await self.logging_cog.send_log(thread.guild.id, embed)

    async def on_thread_update(self, before, after):
        """スレッドの更新を検知してログに記録"""
        try:
            changes = []
        
            # アーカイブ状態の変更を検知
            if before.archived != after.archived:
                status = "クローズ" if after.archived else "再開"
                changes.append(f"スレッドが{status}されました")
            
            # ロック状態の変更を検知
            if before.locked != after.locked:
                status = "ロック" if after.locked else "ロック解除"
                changes.append(f"スレッドが{status}されました")
            
            # スレッド名の変更を検知
            if before.name != after.name:
                changes.append(f"名前が変更されました: {before.name} → {after.name}")
            
            # タグの変更を検知 (フォーラムのスレッドの場合)
            if hasattr(before, 'applied_tags') and hasattr(after, 'applied_tags'):
                before_tags = set(tag.name for tag in before.applied_tags)
                after_tags = set(tag.name for tag in after.applied_tags)
            
                added_tags = after_tags - before_tags
                removed_tags = before_tags - after_tags
            
                if added_tags:
                    changes.append(f"追加されたタグ: {', '.join(added_tags)}")
                if removed_tags:
                    changes.append(f"削除されたタグ: {', '.join(removed_tags)}")
        
            # 権限同期状態の変更を検知
            if hasattr(before, 'permissions_synced') and hasattr(after, 'permissions_synced'):
                if before.permissions_synced != after.permissions_synced:
                    sync_status = "有効" if after.permissions_synced else "無効"
                    changes.append(f"権限の同期が{sync_status}になりました")
        
            if changes:
                embed = discord.Embed(
                    title="スレッド更新",
                    color=discord.Color.yellow()
                )
            
                # スレッド基本情報
                embed.add_field(
                    name="スレッド",
                    value=f"{after.mention}\n親チャンネル: {after.parent.mention}",
                    inline=False
                )
            
                # 変更内容
                embed.add_field(
                    name="変更内容",
                    value="\n".join(changes),
                    inline=False
                )
            
                # 監査ログから変更者と詳細情報を取得
                try:
                    async for entry in after.guild.audit_logs(
                        action=discord.AuditLogAction.thread_update,
                        limit=1
                    ):
                        if entry.target.id == after.id:
                            modifier_name = entry.user.display_name
                            embed.add_field(
                                name="変更者",
                                value=f"{entry.user.mention} ({modifier_name})",
                                inline=False
                            )
                        
                            if entry.reason:
                                embed.add_field(
                                    name="理由",
                                    value=entry.reason,
                                    inline=False
                                )
                            break
                except Exception as e:
                    self.logger.error(f"Error getting audit log in thread update: {e}")
            
                await self.logging_cog.send_log(before.guild.id, embed)

        except Exception as e:
            self.logger.error(f"Error in on_thread_update: {e}")

    async def on_thread_delete(self, thread):
        """スレッド削除の監視"""
        try:
            embed = discord.Embed(
                title="スレッド削除",
                color=discord.Color.red()
            )
            embed.add_field(name="スレッド名", value=thread.name, inline=False)
            embed.add_field(name="親チャンネル", value=thread.parent.name, inline=False)

            # 監査ログから削除者を取得
            async for entry in thread.guild.audit_logs(
                action=discord.AuditLogAction.thread_delete,
                limit=1
            ):
                if entry.target.id == thread.id:
                    embed.add_field(
                        name="削除者",
                        value=f"{entry.user.mention} ({entry.user.display_name})",
                        inline=False
                    )
                    if entry.reason:
                        embed.add_field(name="理由", value=entry.reason, inline=False)
                    break

            await self.logging_cog.send_log(thread.guild.id, embed)
        except Exception as e:
            self.logger.error(f"Error in on_thread_delete: {e}")

    async def on_raw_thread_update(self, payload):
        """タグ変更などの詳細な更新の監視"""
        thread = await self.bot.fetch_channel(payload.thread_id)
        if thread and hasattr(thread, 'applied_tags'):
            try:
                async for entry in thread.guild.audit_logs(limit=1):
                    if (hasattr(entry, 'target') and 
                        entry.target.id == thread.id and 
                        entry.action == discord.AuditLogAction.thread_update):
                        
                        changes = []
                        if hasattr(entry, 'changes'):
                            for change in entry.changes:
                                changes.append(f"{change.key}: {change.before} → {change.after}")
                        
                        if changes:
                            embed = discord.Embed(
                                title="スレッド詳細更新",
                                color=discord.Color.blue()
                            )
                            embed.add_field(
                                name="スレッド",
                                value=f"{thread.mention}\n親チャンネル: {thread.parent.mention}",
                                inline=False
                            )
                            embed.add_field(
                                name="変更内容",
                                value="\n".join(changes),
                                inline=False
                            )
                            await self.logging_cog.send_log(thread.guild.id, embed)
                            
            except Exception as e:
                self.logger.error(f"Error in on_raw_thread_update: {e}")

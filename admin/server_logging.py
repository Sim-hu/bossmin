import discord
from datetime import datetime, timezone
from cogs.constants import PERMISSION_NAMES

class ServerLogging:
    def __init__(self, logging_cog):
        self.logging_cog = logging_cog
        self.bot = logging_cog.bot
        self.logger = logging_cog.logger

    async def on_guild_channel_create(self, channel):
        """チャンネル作成を検知してログに記録"""
        embed = discord.Embed(title="チャンネル作成", color=discord.Color.green())
        embed.add_field(name="チャンネル名", value=channel.name, inline=False)
        embed.add_field(name="種類", value=str(channel.type), inline=False)
        embed.timestamp = datetime.now()
        await self.logging_cog.send_log(channel.guild.id, embed)

    async def on_guild_channel_delete(self, channel):
        """チャンネル削除を検知してログに記録"""
        embed = discord.Embed(title="チャンネル削除", color=discord.Color.red())
        embed.add_field(name="チャンネル名", value=channel.name, inline=False)
        embed.timestamp = datetime.now()
        await self.logging_cog.send_log(channel.guild.id, embed)

    async def on_guild_channel_update(self, before: discord.ForumChannel, after: discord.ForumChannel):
        """フォーラムチャンネルの更新を監視"""
        if not isinstance(before, discord.ForumChannel) or not isinstance(after, discord.ForumChannel):
            return

        try:
            changes = []
            
            # フォーラム設定の変更を検知
            # 投稿ガイドライン
            if before.topic != after.topic:
                before_guide = before.topic or "なし"
                after_guide = after.topic or "なし"
                changes.append({
                    "name": "投稿ガイドライン",
                    "value": f"変更前:\n```\n{before_guide}\n```\n変更後:\n```\n{after_guide}\n```"
                })

            # デフォルトの自動アーカイブ時間
            if before.default_auto_archive_duration != after.default_auto_archive_duration:
                changes.append({
                    "name": "デフォルトアーカイブ時間",
                    "value": f"{before.default_auto_archive_duration}分 → {after.default_auto_archive_duration}分"
                })

            # デフォルトのスレッド低速モード
            if before.default_thread_slowmode_delay != after.default_thread_slowmode_delay:
                before_slow = before.default_thread_slowmode_delay or 0
                after_slow = after.default_thread_slowmode_delay or 0
                changes.append({
                    "name": "デフォルト低速モード",
                    "value": f"{before_slow}秒 → {after_slow}秒"
                })

            # NSFW設定
            if before.nsfw != after.nsfw:
                changes.append({
                    "name": "NSFW設定",
                    "value": f"{'有効' if before.nsfw else '無効'} → {'有効' if after.nsfw else '無効'}"
                })

            # タグの必須設定
            if hasattr(before, 'required_tags') and hasattr(after, 'required_tags'):
                if before.required_tags != after.required_tags:
                    changes.append({
                        "name": "必須タグ数",
                        "value": f"{before.required_tags}個 → {after.required_tags}個"
                    })

            # タグの変更を検知
            before_tags = {tag.name: tag for tag in before.available_tags}
            after_tags = {tag.name: tag for tag in after.available_tags}
            
            # 新規作成されたタグを検出
            added_tags = []
            for tag_name, tag in after_tags.items():
                if tag_name not in before_tags:
                    emoji_str = str(tag.emoji) if tag.emoji else "なし"
                    modifiable = "変更可能" if tag.moderated else "変更不可"
                    added_tags.append(f"名前: {tag_name}\n  絵文字: {emoji_str}\n  {modifiable}")
            
            if added_tags:
                changes.append({
                    "name": "追加されたタグ",
                    "value": "```\n" + "\n\n".join(added_tags) + "\n```"
                })
            
            # 削除されたタグを検出
            removed_tags = []
            for tag_name, tag in before_tags.items():
                if tag_name not in after_tags:
                    emoji_str = str(tag.emoji) if tag.emoji else "なし"
                    modifiable = "変更可能" if tag.moderated else "変更不可"
                    removed_tags.append(f"名前: {tag_name}\n  絵文字: {emoji_str}\n  {modifiable}")
            
            if removed_tags:
                changes.append({
                    "name": "削除されたタグ",
                    "value": "```\n" + "\n\n".join(removed_tags) + "\n```"
                })
            
            # 既存タグの変更を検出
            modified_tags = []
            for tag_name in set(before_tags.keys()) & set(after_tags.keys()):
                before_tag = before_tags[tag_name]
                after_tag = after_tags[tag_name]
                
                changes_in_tag = []
                
                if before_tag.emoji != after_tag.emoji:
                    before_emoji = str(before_tag.emoji) if before_tag.emoji else "なし"
                    after_emoji = str(after_tag.emoji) if after_tag.emoji else "なし"
                    changes_in_tag.append(f"  絵文字: {before_emoji} → {after_emoji}")
                
                if before_tag.moderated != after_tag.moderated:
                    before_mod = "変更可能" if before_tag.moderated else "変更不可"
                    after_mod = "変更可能" if after_tag.moderated else "変更不可"
                    changes_in_tag.append(f"  設定: {before_mod} → {after_mod}")
                
                if changes_in_tag:
                    modified_tags.append(f"名前: {tag_name}\n" + "\n".join(changes_in_tag))
            
            if modified_tags:
                changes.append({
                    "name": "変更されたタグ",
                    "value": "```\n" + "\n\n".join(modified_tags) + "\n```"
                })

            if changes:
                embed = discord.Embed(
                    title="フォーラム設定更新",
                    color=discord.Color.blue(),
                    description=f"フォーラム: {after.mention}"
                )

                # 変更内容を埋め込みに追加
                for change in changes:
                    embed.add_field(
                        name=change["name"],
                        value=change["value"],
                        inline=False
                    )

                # 変更者の情報を取得
                try:
                    async for entry in after.guild.audit_logs(
                        action=discord.AuditLogAction.channel_update,
                        limit=1
                    ):
                        if entry.target.id == after.id:
                            embed.add_field(
                                name="変更者",
                                value=f"{entry.user.mention} ({entry.user.display_name})",
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
                    self.logger.error(f"Error getting audit log for forum update: {e}")

                await self.logging_cog.send_log(after.guild.id, embed)

        except Exception as e:
            self.logger.error(f"Error in on_guild_channel_update: {e}")

    async def on_guild_update(self, before, after):
        """サーバー設定の更新を検知してログに記録"""
        changes = []
    
        # サーバー基本設定の変更検知
        if before.name != after.name:
            changes.append(f"サーバー名: {before.name} → {after.name}")
        if before.icon != after.icon:
            changes.append("サーバーアイコンが変更されました")
        if before.banner != after.banner:
            changes.append("サーバーバナーが変更されました")
        if before.description != after.description:
            changes.append(f"説明: {before.description} → {after.description}")
        if before.verification_level != after.verification_level:
            changes.append(f"認証レベル: {before.verification_level} → {after.verification_level}")
        
        # ブーストレベルの変更検知
        if before.premium_tier != after.premium_tier:
            embed = discord.Embed(title="サーバーブーストレベル変更", color=discord.Color.purple())
            embed.add_field(name="変更前", value=f"レベル {before.premium_tier}")
            embed.add_field(name="変更後", value=f"レベル {after.premium_tier}")
            embed.add_field(name="ブースト数", value=str(after.premium_subscription_count))
            await self.logging_cog.send_log(after.id, embed)

        # その他の変更がある場合の通知
        if changes:
            embed = discord.Embed(title="サーバー設定変更", color=discord.Color.blue())
            embed.description = "\n".join(changes)
        
            # 監査ログから変更者を取得
            async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
                embed.add_field(name="変更者", value=entry.user.mention)
                break
            
            await self.logging_cog.send_log(after.id, embed)

    async def on_guild_emojis_update(self, guild, before, after):
        """絵文字の更新を検知してログに記録"""
        added = set(after) - set(before)
        removed = set(before) - set(after)
    
        if added:
            embed = discord.Embed(title="絵文字追加", color=discord.Color.green())
            for emoji in added:
                embed.add_field(name=emoji.name, value=str(emoji), inline=True)
            await self.logging_cog.send_log(guild.id, embed)
    
        if removed:
            embed = discord.Embed(title="絵文字削除", color=discord.Color.red())
            for emoji in removed:
                embed.add_field(name=emoji.name, value=str(emoji), inline=True)
            await self.logging_cog.send_log(guild.id, embed)

    async def on_guild_stickers_update(self, guild, before, after):
        """スティッカーの更新を検知してログに記録"""
        added = set(after) - set(before)
        removed = set(before) - set(after)
    
        if added:
            embed = discord.Embed(title="スティッカー追加", color=discord.Color.green())
            for sticker in added:
                embed.add_field(name=sticker.name, value=sticker.description, inline=False)
            await self.logging_cog.send_log(guild.id, embed)

    async def on_guild_role_update(self, before, after):
        """ロールの更新を検知してログに記録"""
        changes = []
    
        # 名前の変更
        if before.name != after.name:
            changes.append(f"📝 **名前**\n`{before.name}` → `{after.name}`")
    
        # 色の変更
        if before.color != after.color:
            # 色をHEX形式で表示
            before_color = f"#{before.color.value:0>6x}" if before.color.value else "なし"
            after_color = f"#{after.color.value:0>6x}" if after.color.value else "なし"
            changes.append(f"🎨 **色**\n{before_color} → {after_color}")
    
        # メンバー一覧表示の変更
        if before.hoist != after.hoist:
            status = {True: "する", False: "しない"}
            changes.append(f"📊 **メンバー一覧に表示**\n{status[before.hoist]} → {status[after.hoist]}")
    
        # メンション可否の変更
        if before.mentionable != after.mentionable:
            status = {True: "可能", False: "不可"}
            changes.append(f"💬 **メンション**\n{status[before.mentionable]} → {status[after.mentionable]}")
    
        # 権限の変更
        if before.permissions != after.permissions:
            before_perms = dict(before.permissions)
            after_perms = dict(after.permissions)
            
            permission_changes = []
            
            # 権限の状態を表す絵文字
            status_emoji = {
                True: "✅",    # 許可
                False: "❌",   # 拒否
            }
            
            # すべての権限をチェック
            for perm in set(before_perms.keys()) | set(after_perms.keys()):
                if before_perms.get(perm) != after_perms.get(perm):
                    perm_name = PERMISSION_NAMES.get(perm, perm)
                    before_value = before_perms.get(perm, False)
                    after_value = after_perms.get(perm, False)
                    permission_changes.append(f"・{perm_name}：{status_emoji[before_value]} → {status_emoji[after_value]}")
            
            if permission_changes:
                changes.append("🔧 **権限変更**\n" + "\n".join(sorted(permission_changes)))
    
        if changes:
            embed = discord.Embed(
                title="🔄 ロール設定変更",
                description=f"ロール: {after.mention}",
                color=after.color or discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # 変更内容が1024文字を超える場合は分割
            content = "\n\n".join(changes)
            if len(content) > 1024:
                for i, chunk in enumerate(changes, 1):
                    embed.add_field(
                        name=f"変更内容 {i}",
                        value=chunk,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="変更内容",
                    value=content,
                    inline=False
                )
    
            # 監査ログから変更者を取得
            try:
                async for entry in after.guild.audit_logs(
                    action=discord.AuditLogAction.role_update,
                    limit=1
                ):
                    if entry.target.id == after.id:
                        embed.add_field(
                            name="👤 変更者",
                            value=f"{entry.user.mention} (`{entry.user.name}`)",
                            inline=False
                        )
                        if entry.reason:
                            embed.add_field(
                                name="📝 変更理由",
                                value=entry.reason,
                                inline=False
                            )
                        break
            except Exception as e:
                self.logger.error(f"監査ログの取得中にエラーが発生しました: {e}")
    
            await self.logging_cog.send_log(after.guild.id, embed)

    async def on_guild_integrations_update(self, guild):
        """
        インテグレーションの追加/削除/更新を検知するリスナー
        具体的には以下の変更を検知:
        - Botの追加/削除
        - Webhookの作成/更新/削除
        - アプリケーションの連携
        """
        async for entry in guild.audit_logs(limit=1):
            if entry.action in [
                discord.AuditLogAction.integration_create,
                discord.AuditLogAction.integration_update,
                discord.AuditLogAction.integration_delete,
                discord.AuditLogAction.webhook_create,
                discord.AuditLogAction.webhook_update,
                discord.AuditLogAction.webhook_delete,
                discord.AuditLogAction.bot_add
            ]:
                embed = discord.Embed(
                    title="インテグレーション更新", 
                    color=discord.Color.blue()
                )
                embed.add_field(name="実行者", value=entry.user.mention)
                embed.add_field(name="アクション", value=str(entry.action))
                if entry.target:
                    embed.add_field(name="対象", value=str(entry.target))
                if entry.reason:
                    embed.add_field(name="理由", value=entry.reason)
                await self.logging_cog.send_log(guild.id, embed)

    async def on_invite_create(self, invite):
        """招待リンクの作成を検知してログに記録"""
        embed = discord.Embed(title="招待リンク作成", color=discord.Color.green())
        embed.add_field(name="作成者", value=invite.inviter.mention)
        embed.add_field(name="チャンネル", value=invite.channel.mention)
        embed.add_field(name="使用可能回数", value=str(invite.max_uses or "無制限"))
        embed.add_field(name="有効期限", value=str(invite.max_age or "無期限"))
        await self.logging_cog.send_log(invite.guild.id, embed)

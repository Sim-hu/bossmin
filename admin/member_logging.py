import discord
from datetime import datetime, timezone

class MemberLogging:
    def __init__(self, logging_cog):
        self.logging_cog = logging_cog
        self.bot = logging_cog.bot
        self.logger = logging_cog.logger

    async def on_member_update(self, before, after):
        """メンバー情報の更新を検知してログに記録"""
        # ニックネームの変更を検知
        if before.nick != after.nick:
            embed = discord.Embed(title="ニックネーム変更", color=discord.Color.green())
            embed.add_field(name="メンバー", value=f"{before.mention} ({before.name})", inline=False)
            embed.add_field(name="変更前", value=before.nick or before.name, inline=False)
            embed.add_field(name="変更後", value=after.nick or after.name, inline=False)

            # 監査ログから変更者を取得
            async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
                if entry.target.id == after.id and entry.changes.before.nick != entry.changes.after.nick:
                    modifier_name = entry.user.display_name
                    embed.add_field(name="変更者", value=f"{entry.user.mention} ({modifier_name})", inline=False)
                    break

            embed.timestamp = datetime.now()
            await self.logging_cog.send_log(before.guild.id, embed)

        # タイムアウトの検知と解除
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until is not None:
                embed = discord.Embed(title="メンバータイムアウト", color=discord.Color.orange())
                embed.add_field(name="メンバー", value=f"{after.mention}", inline=False)
                embed.add_field(name="期限", value=f"<t:{int(after.timed_out_until.timestamp())}:F>", inline=False)
            else:
                embed = discord.Embed(title="タイムアウト解除", color=discord.Color.green())
                embed.add_field(name="メンバー", value=after.mention)
        
            # 監査ログから実行者を取得
            async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=1):
                if entry.target.id == after.id:
                    executor_name = entry.user.display_name
                    embed.add_field(name="実行者", value=f"{entry.user.mention} ({executor_name})", inline=False)
                    break
        
            embed.timestamp = datetime.now()
            await self.logging_cog.send_log(after.guild.id, embed)

        # アバター変更の検知
        if before.display_avatar != after.display_avatar:
            embed = discord.Embed(title="アバター変更", color=discord.Color.blue())
            embed.add_field(name="メンバー", value=after.mention)
            if before.display_avatar:
                embed.set_thumbnail(url=before.display_avatar.url)
            if after.display_avatar:
                embed.set_image(url=after.display_avatar.url)
            await self.logging_cog.send_log(after.guild.id, embed)

        # ロールの変更を検知
        if before.roles != after.roles:
            # 追加されたロール
            added_roles = set(after.roles) - set(before.roles)
            # 削除されたロール
            removed_roles = set(before.roles) - set(after.roles)

            if added_roles:
                embed = discord.Embed(title="ロール追加", color=discord.Color.green())
                member_name = after.display_name
                embed.add_field(name="メンバー", value=f"{after.mention} ({member_name})", inline=False)
                embed.add_field(name="追加されたロール", value=", ".join([role.mention for role in added_roles]), inline=False)

                # 監査ログから追加者を取得
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
                    if entry.target.id == after.id:
                        modifier_name = entry.user.display_name
                        embed.add_field(name="実行者", value=f"{entry.user.mention} ({modifier_name})", inline=False)
                        break

                embed.timestamp = datetime.now()
                await self.logging_cog.send_log(after.guild.id, embed)

            if removed_roles:
                embed = discord.Embed(title="ロール削除", color=discord.Color.red())
                member_name = after.display_name
                embed.add_field(name="メンバー", value=f"{after.mention} ({member_name})", inline=False)
                embed.add_field(name="削除されたロール", value=", ".join([role.mention for role in removed_roles]), inline=False)

                # 監査ログから削除者を取得
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
                    if entry.target.id == after.id:
                        modifier_name = entry.user.display_name
                        embed.add_field(name="実行者", value=f"{entry.user.mention} ({modifier_name})", inline=False)
                        break

                embed.timestamp = datetime.now()
                await self.logging_cog.send_log(after.guild.id, embed)

    async def on_member_join(self, member):
        """メンバーの参加を検知してログに記録"""
        embed = discord.Embed(title="メンバー参加", color=discord.Color.green())
        member_name = member.display_name

        # メンバー情報とアイコンを設定
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.description = f"{member.mention} ({member_name})がサーバーに参加しました"

        # アカウント作成日を追加
        created_at_timestamp = int(member.created_at.timestamp())
        embed.add_field(
            name="アカウントの年齢",
            value=f"<t:{created_at_timestamp}:R>\n<t:{created_at_timestamp}:F>",
            inline=False
        )
        
        embed.timestamp = datetime.now()
        await self.logging_cog.send_log(member.guild.id, embed)

    async def on_member_remove(self, member):
        """メンバーの退出またはキックを検知してログに記録"""
        try:
            async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
                # datetime.now()にタイムゾーン情報を追加
                current_time = datetime.now(timezone.utc)
                
                if entry.target.id == member.id and (current_time - entry.created_at).total_seconds() < 5:
                    # キック処理
                    embed = discord.Embed(title="メンバーキック", color=discord.Color.red())
                    embed.add_field(name="対象者", value=f"{member} (`{member.id}`)", inline=False)
                    embed.add_field(name="実行者", value=f"{entry.user} (`{entry.user.id}`)", inline=False)
                    if entry.reason:
                        embed.add_field(name="理由", value=entry.reason, inline=False)
                    embed.timestamp = current_time
                    await self.logging_cog.send_log(member.guild.id, embed)
                    return

            # キックではない場合（サーバー退出）
            current_time = datetime.now(timezone.utc)
            embed = discord.Embed(title="メンバー退出", color=discord.Color.orange())
            embed.add_field(name="ユーザー", value=f"{member} (`{member.id}`)", inline=False)
            embed.add_field(name="アカウント作成日", value=member.created_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
            embed.add_field(name="参加日時", value=member.joined_at.strftime('%Y-%m-%d %H:%M:%S'), inline=False)
            embed.timestamp = current_time
            await self.logging_cog.send_log(member.guild.id, embed)

        except Exception as e:
            self.logger.error(f"Error in on_member_remove: {e}")

    async def on_member_ban(self, guild, user):
        """メンバーのBANを検知してログに記録"""
        embed = discord.Embed(title="メンバーBAN", color=discord.Color.dark_red())
        embed.add_field(name="メンバー", value=f"{user.mention} ({user.display_name})", inline=False)
        
        # 監査ログから実行者とBANの理由を取得
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if entry.target.id == user.id:
                executor_name = entry.user.display_name
                embed.add_field(name="実行者", value=f"{entry.user.mention} ({executor_name})", inline=False)
                if entry.reason:
                    embed.add_field(name="理由", value=entry.reason, inline=False)
                break
        
        embed.timestamp = datetime.now()
        await self.logging_cog.send_log(guild.id, embed)

    async def on_member_unban(self, guild, user):
        """メンバーのBAN解除を検知してログに記録"""
        embed = discord.Embed(title="メンバーBAN解除", color=discord.Color.green())
        embed.add_field(name="メンバー", value=f"{user.mention} ({user.display_name})", inline=False)
        
        # 監査ログから実行者を取得
        async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=1):
            if entry.target.id == user.id:
                executor_name = entry.user.display_name
                embed.add_field(name="実行者", value=f"{entry.user.mention} ({executor_name})", inline=False)
                if entry.reason:
                    embed.add_field(name="理由", value=entry.reason, inline=False)
                break
        
        embed.timestamp = datetime.now()
        await self.logging_cog.send_log(guild.id, embed)

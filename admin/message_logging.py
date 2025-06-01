import discord
from datetime import datetime, timezone
from typing import List
import io

class MessageLogging:
    def __init__(self, logging_cog):
        self.logging_cog = logging_cog
        self.bot = logging_cog.bot
        self.logger = logging_cog.logger

    async def on_message(self, message):
        """メッセージの投稿を記録"""
        if message.author.bot:
            return
        self.logger.info(f"{message.guild.name} - #{message.channel.name}: {message.author.name}: {message.content}")

    async def on_message_edit(self, before, after):
        """メッセージの編集を検知してログに記録"""
        if before.author.bot:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(
            title="メッセージ編集",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="チャンネル", value=f"{before.channel.mention}", inline=False)
        editor_name = before.author.display_name
        embed.add_field(name="編集者", value=f"{before.author.mention} ({editor_name})", inline=False)
        
        # 編集前後のコンテンツを追加
        if len(before.content) > 1024:
            embed.add_field(name="編集前", value=f"{before.content[:1021]}...", inline=False)
        else:
            embed.add_field(name="編集前", value=before.content or "（空メッセージ）", inline=False)
            
        if len(after.content) > 1024:
            embed.add_field(name="編集後", value=f"{after.content[:1021]}...", inline=False)
        else:
            embed.add_field(name="編集後", value=after.content or "（空メッセージ）", inline=False)

        await self.logging_cog.send_log(before.guild.id, embed)

    async def on_message_delete(self, message):
        """メッセージの削除を検知してログに記録"""
        if message.author.bot:
            return
    
        embed = discord.Embed(title="メッセージ削除", color=discord.Color.red())
        embed.add_field(name="チャンネル", value=f"{message.channel.mention} (`{message.channel.name}`)", inline=False)
        author_name = message.author.display_name
        embed.add_field(name="投稿者", value=f"{message.author.mention} (`{author_name}`)", inline=False)
        
        # メッセージ内容の処理
        if message.content:
            if len(message.content) > 1024:
                embed.add_field(name="内容", value=f"{message.content[:1021]}...", inline=False)
            else:
                embed.add_field(name="内容", value=message.content, inline=False)
    
        # 添付ファイルの処理
        if message.attachments:
            try:
                archive_channel = self.logging_cog.get_archive_channel()
                if archive_channel:
                    archive_embed = discord.Embed(
                        title="削除された画像のアーカイブ",
                        color=discord.Color.blue(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    archive_embed.add_field(
                        name="元のサーバー",
                        value=f"{message.guild.name} (`{message.guild.id}`)",
                        inline=False
                    )
                    archive_embed.add_field(
                        name="元のチャンネル",
                        value=f"#{message.channel.name} (`{message.channel.id}`)",
                        inline=False
                    )
                    archive_embed.add_field(
                        name="投稿者",
                        value=f"{message.author.name} (`{message.author.id}`)",
                        inline=False
                    )

                    attachment_info = []
                    for i, attachment in enumerate(message.attachments, 1):
                        try:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                # 画像をダウンロード
                                img_data = await attachment.read()
                                
                                # 画像ファイルを作成
                                file = discord.File(
                                    io.BytesIO(img_data),
                                    filename=attachment.filename
                                )
                                
                                # アーカイブチャンネルに送信
                                archive_msg = await archive_channel.send(
                                    embed=archive_embed,
                                    file=file
                                )
                                
                                # 元のログ用の情報を追加
                                if archive_msg.attachments:
                                    attachment_info.append(f"画像 {i}:")
                                    attachment_info.append(f"- 名前: {attachment.filename}")
                                    attachment_info.append(f"- アーカイブ: [リンク]({archive_msg.attachments[0].url})")
                                    if hasattr(attachment, 'width') and hasattr(attachment, 'height'):
                                        attachment_info.append(f"- 寸法: {attachment.width}x{attachment.height}")
                            else:
                                # 画像以外の添付ファイル情報
                                attachment_info.append(f"添付ファイル {i}:")
                                attachment_info.append(f"- 名前: {attachment.filename}")
                                attachment_info.append(f"- タイプ: {attachment.content_type or '不明'}")
                                attachment_info.append(f"- サイズ: {attachment.size:,} bytes")
                                
                        except Exception as e:
                            self.logger.error(f"Error processing attachment {i}: {e}")
                            attachment_info.append(f"添付ファイル {i}: 処理中にエラーが発生しました")

                    # 添付ファイル情報をフィールドとして追加
                    if attachment_info:
                        attachment_text = "\n".join(attachment_info)
                        if len(attachment_text) > 1024:
                            attachment_text = f"{attachment_text[:1021]}..."
                        embed.add_field(name="添付ファイル情報", value=attachment_text, inline=False)

            except Exception as e:
                self.logger.error(f"Error archiving images: {e}")
                embed.add_field(
                    name="エラー",
                    value=f"画像のアーカイブ中にエラーが発生しました: {str(e)}",
                    inline=False
                )
    
        # 監査ログから削除者を取得
        try:
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1):
                entry_time = entry.created_at
                current_time = datetime.now(timezone.utc)
                
                if entry.target.id == message.author.id and (current_time - entry_time).total_seconds() < 5:
                    deleter_name = entry.user.display_name
                    embed.add_field(name="削除者", value=f"{entry.user.mention} (`{deleter_name}`)", inline=False)
                    break
        except Exception as e:
            self.logger.error(f"Error getting audit log for message delete: {e}")
    
        embed.timestamp = datetime.now()
        await self.logging_cog.send_log(message.guild.id, embed, log_type='general')

    async def delete_messages_safely(self, messages: List[discord.Message], interaction: discord.Interaction) -> tuple[int, int, int]:
        """
        メッセージを安全に削除する補助関数
        Returns: (削除成功数, 14日超過数, エラー数)
        """
        now = datetime.now(timezone.utc)
        deletable = []
        old_messages = 0
        
        # メッセージを分類
        for message in messages:
            if (now - message.created_at).days >= 14:
                old_messages += 1
                continue
            deletable.append(message)
        
        # 100件ずつに分割して削除
        deleted = 0
        error_count = 0
        
        for i in range(0, len(deletable), 100):
            chunk = deletable[i:i + 100]
            try:
                if len(chunk) > 1:
                    await interaction.channel.delete_messages(chunk)
                    deleted += len(chunk)
                elif len(chunk) == 1:
                    await chunk[0].delete()
                    deleted += 1
            except discord.HTTPException as e:
                error_count += len(chunk)
                self.logger.error(f"メッセージ削除中にエラー: {e}")
                
        return deleted, old_messages, error_count

    async def on_bulk_message_delete(self, messages):
        """
        メッセージの一括削除を検知し、削除されたメッセージの内容をファイルとして保存・送信する
        画像が含まれている場合は指定されたアーカイブチャンネルに保存する
        """
        if not messages:
            return
        
        guild = messages[0].guild
        channel = messages[0].channel
        
        embed = discord.Embed(
            title="メッセージ一括削除",
            description=f"チャンネル: {channel.mention} (`{channel.name}`)",
            color=discord.Color.red()
        )
        
        # メッセージの分析
        total_messages = len(messages)
        now = datetime.now(timezone.utc)
        old_messages = sum(1 for msg in messages if (now - msg.created_at).days >= 14)
        
        embed.add_field(
            name="削除状態",
            value=f"削除試行数: {total_messages}\n"
                  f"14日以上経過: {old_messages}件\n"
                  f"14日未満: {total_messages - old_messages}件",
            inline=False
        )
        
        # 画像を含むメッセージの処理
        archive_channel = self.logging_cog.get_archive_channel()  # 引数なしで呼び出し
        image_archive_count = 0
        
        # メッセージ内容をファイルとして保存
        content = []
        for msg in sorted(messages, key=lambda x: x.created_at):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{msg.author.name}"
            age_days = (now - msg.created_at).days
            
            content.append(f"[{timestamp}] {author}: {msg.content}")
            
            # 添付ファイルの処理
            if msg.attachments and archive_channel:
                archive_embed = discord.Embed(
                    title="一括削除された画像のアーカイブ",
                    color=discord.Color.blue(),
                    timestamp=now
                )
                archive_embed.add_field(
                    name="元のサーバー",
                    value=f"{guild.name} (`{guild.id}`)",
                    inline=False
                )
                archive_embed.add_field(
                    name="元のチャンネル",
                    value=f"#{channel.name} (`{channel.id}`)",
                    inline=False
                )
                archive_embed.add_field(
                    name="投稿者",
                    value=f"{author} (`{msg.author.id}`)",
                    inline=False
                )
                archive_embed.add_field(
                    name="投稿日時",
                    value=timestamp,
                    inline=False
                )

                for attachment in msg.attachments:
                    try:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            # 画像をダウンロード
                            img_data = await attachment.read()
                            file = discord.File(
                                io.BytesIO(img_data),
                                filename=attachment.filename
                            )
                            
                            # アーカイブチャンネルに送信
                            archive_msg = await archive_channel.send(
                                embed=archive_embed,
                                file=file
                            )
                            
                            # ログ用の情報を追加
                            content.append(f"  画像: {attachment.filename}")
                            content.append(f"  アーカイブ: {archive_msg.attachments[0].url}")
                            if hasattr(attachment, 'width') and hasattr(attachment, 'height'):
                                content.append(f"  寸法: {attachment.width}x{attachment.height}")
                            
                            image_archive_count += 1
                        else:
                            # 画像以外の添付ファイル情報
                            content.append(f"  添付ファイル: {attachment.filename}")
                            content.append(f"  タイプ: {attachment.content_type or '不明'}")
                            content.append(f"  サイズ: {attachment.size:,} bytes")
                    except Exception as e:
                        self.logger.error(f"Error archiving image in bulk delete: {e}")
                        content.append(f"  画像アーカイブ中にエラー: {attachment.filename}")
            
            content.append(f"  (経過日数: {age_days}日)")
            content.append("---")
        
        # アーカイブ状況を追加
        if image_archive_count > 0:
            embed.add_field(
                name="画像アーカイブ",
                value=f"{image_archive_count}件の画像をアーカイブしました。",
                inline=False
            )
        
        # 削除ログファイルの作成
        content_text = "\n".join(content)
        file = discord.File(
            io.StringIO(content_text),
            filename=f"deleted_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        # 監査ログから削除者を取得
        try:
            async for entry in guild.audit_logs(
                action=discord.AuditLogAction.message_bulk_delete,
                limit=1
            ):
                deleter = entry.user
                embed.add_field(
                    name="実行者",
                    value=f"{deleter.mention} (`{deleter.name}`)",
                    inline=False
                )
                if entry.reason:
                    embed.add_field(name="理由", value=entry.reason, inline=False)
                break
        except discord.Forbidden:
            embed.add_field(
                name="注意",
                value="監査ログの取得権限がないため、削除者の情報は取得できませんでした。",
                inline=False
            )
        except Exception as e:
            self.logger.error(f"監査ログの取得中にエラーが発生: {e}")
        
        # 警告メッセージの追加
        if old_messages > 0:
            embed.add_field(
                name="⚠️ 注意",
                value="14日以上経過したメッセージは一括削除できません。\n"
                      "これらのメッセージは手動で個別に削除する必要があります。",
                inline=False
            )
        
        if total_messages > 100:
            embed.add_field(
                name="⚠️ 制限",
                value="一度に削除できるメッセージは100件までです。\n"
                      "100件を超えるメッセージを削除する場合は、複数回に分けて実行してください。",
                inline=False
            )
        
        embed.timestamp = now
        
        # ログチャンネルへの送信
        try:
            if str(guild.id) in self.logging_cog.log_channels:
                log_channel = self.bot.get_channel(int(self.logging_cog.log_channels[str(guild.id)]))
                if log_channel:
                    await log_channel.send(embed=embed, file=file)
                else:
                    self.logger.error(f"ログチャンネルが見つかりません: {guild.name} ({guild.id})")
            else:
                self.logger.info(f"ログチャンネルが設定されていません: {guild.name} ({guild.id})")
        except Exception as e:
            self.logger.error(f"ログの送信中にエラーが発生: {e}")

import discord
from datetime import datetime, timezone

class VoiceLogging:
    def __init__(self, logging_cog):
        self.logging_cog = logging_cog
        self.bot = logging_cog.bot
        self.logger = logging_cog.logger

    async def on_voice_state_update(self, member, before, after):
        """
        ボイスチャンネルの参加/退出を検知してログを送信する
        
        Parameters:
        -----------
        member : discord.Member
            状態が変更されたメンバー
        before : discord.VoiceState
            変更前の状態
        after : discord.VoiceState
            変更後の状態
        """
        if before.channel != after.channel:
            now = datetime.now(timezone.utc)  # UTCタイムゾーンを使用
    
            if after.channel:
                # VC参加時のembed作成
                embed = discord.Embed(
                    title="VC参加", 
                    color=discord.Color.green(),
                    timestamp=now
                )
                embed.add_field(
                    name="メンバー", 
                    value=f"{member.mention} (`{member.display_name}`)", 
                    inline=False
                )
                embed.add_field(
                    name="チャンネル", 
                    value=f"{after.channel.mention} (`{after.channel.name}`)", 
                    inline=False
                )
                embed.set_footer(text=f"User ID: {member.id}")
    
            elif before.channel:
                # VC退出時のembed作成
                embed = discord.Embed(
                    title="VC退出", 
                    color=discord.Color.red(),
                    timestamp=now
                )
                embed.add_field(
                    name="メンバー", 
                    value=f"{member.mention} (`{member.display_name}`)", 
                    inline=False
                )
                embed.add_field(
                    name="チャンネル", 
                    value=f"{before.channel.mention} (`{before.channel.name}`)", 
                    inline=False
                )
                embed.set_footer(text=f"User ID: {member.id}")
    
            try:
                # 新しいsend_log関数を使用してログを送信
                # VCログはlog_type='vc'として送信
                await self.logging_cog.send_log(member.guild.id, embed, log_type='vc')
            except Exception as e:
                self.logger.error(f"VCログの送信中にエラーが発生しました: {e}")

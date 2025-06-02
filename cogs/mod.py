import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import asyncio
import logging
import re
from typing import Literal, Optional
from utils.checks import BaseCog

# 例外パターンを保存するファイル
EXCEPTIONS_FILE = 'data/mod_exceptions.json'

class ModerationCog(BaseCog):
    """
    Discordサーバー内の特定の装飾（取り消し線、スポイラー）を検出・削除するモデレーション機能
    """
    
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.logger = logging.getLogger("bot.mod")
        
        # データディレクトリの確認と作成
        os.makedirs('data', exist_ok=True)
        
        # 例外パターンを読み込む
        self.load_exceptions()
    
    def load_exceptions(self):
        """例外パターンを読み込む"""
        try:
            if os.path.exists(EXCEPTIONS_FILE):
                with open(EXCEPTIONS_FILE, 'r', encoding='utf-8') as f:
                    self.exceptions = json.load(f)
                    # 正規表現パターンをコンパイル
                    self.compile_regex_patterns()
                    self.logger.info(f"例外パターンを読み込みました: {len(self.exceptions['strikethrough'])}個の取り消し線, {len(self.exceptions['spoiler'])}個のスポイラー")
            else:
                self.exceptions = {
                    "strikethrough": [],  # 取り消し線の例外パターン
                    "spoiler": []         # スポイラーの例外パターン
                }
                self.save_exceptions()
                # 空のコンパイル済み正規表現リスト
                self.strikethrough_regex = []
                self.spoiler_regex = []
                self.logger.info("例外パターンのファイルが存在しないため、新規作成しました")
        except Exception as e:
            self.logger.error(f"例外パターンの読み込み中にエラーが発生しました: {e}")
            # 読み込みに失敗した場合、デフォルト値を設定
            self.exceptions = {
                "strikethrough": [],
                "spoiler": []
            }
            # 空のコンパイル済み正規表現リスト
            self.strikethrough_regex = []
            self.spoiler_regex = []
    
    def compile_regex_patterns(self):
        """例外パターンを正規表現としてコンパイルする"""
        try:
            self.strikethrough_regex = []
            self.spoiler_regex = []
            
            for pattern in self.exceptions["strikethrough"]:
                # パターンを正規表現としてコンパイル
                # ^ と $ で囲み、完全一致を確認
                self.strikethrough_regex.append(re.compile(f"^{re.escape(pattern)}$"))
            
            for pattern in self.exceptions["spoiler"]:
                # パターンを正規表現としてコンパイル
                self.spoiler_regex.append(re.compile(f"^{re.escape(pattern)}$"))
                
            self.logger.debug("正規表現パターンをコンパイルしました")
        except Exception as e:
            self.logger.error(f"正規表現パターンのコンパイル中にエラーが発生しました: {e}")
    
    def save_exceptions(self):
        """例外パターンを保存する"""
        try:
            with open(EXCEPTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.exceptions, f, ensure_ascii=False, indent=4)
                self.logger.debug("例外パターンを保存しました")
            # 保存後に正規表現パターンを再コンパイル
            self.compile_regex_patterns()
        except Exception as e:
            self.logger.error(f"例外パターンの保存中にエラーが発生しました: {e}")
    
    def extract_decorated_text(self, content, decoration_type):
        """装飾されたテキストを抽出する"""
        if decoration_type == "strikethrough":
            # 取り消し線で囲まれたテキストを抽出
            pattern = r"~~(.*?)~~"
        else:  # spoiler
            # スポイラーで囲まれたテキストを抽出
            pattern = r"\|\|(.*?)\|\|"
        
        matches = re.findall(pattern, content)
        return matches
    
    def is_exception_match(self, text, decoration_type):
        """抽出されたテキストが例外パターンに一致するかをチェック"""
        if decoration_type == "strikethrough":
            regex_list = self.strikethrough_regex
        else:  # spoiler
            regex_list = self.spoiler_regex
        
        # 正規表現パターンとのマッチングをチェック
        for regex in regex_list:
            if regex.match(text):
                return True
        
        return False
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """メッセージが送信されたときのイベントハンドラ"""
        # ボット自身のメッセージは無視
        if message.author.bot:
            return
        
        # DMは処理しない
        if not isinstance(message.channel, discord.TextChannel):
            return
        
        try:
            # メッセージに装飾が含まれているか確認
            content = message.content
            has_strikethrough = '~~' in content
            has_spoiler = '||' in content
            
            # 取り消し線の処理
            if has_strikethrough:
                decorated_texts = self.extract_decorated_text(content, "strikethrough")
                all_match_exception = True
                
                # 取り消し線内の全てのテキストがいずれかの例外パターンに一致するか確認
                for text in decorated_texts:
                    if not self.is_exception_match(text, "strikethrough"):
                        all_match_exception = False
                        break
                
                # 一つでも例外パターンに一致しないものがあれば削除
                if not all_match_exception and decorated_texts:
                    await self.delete_and_warn(message, "取り消し線")
                    self.logger.info(f"取り消し線が含まれるメッセージを削除しました - サーバー: {message.guild.id}, チャンネル: {message.channel.id}, ユーザー: {message.author.id}")
                    return
            
            # スポイラーの処理
            if has_spoiler:
                decorated_texts = self.extract_decorated_text(content, "spoiler")
                all_match_exception = True
                
                # スポイラー内の全てのテキストがいずれかの例外パターンに一致するか確認
                for text in decorated_texts:
                    if not self.is_exception_match(text, "spoiler"):
                        all_match_exception = False
                        break
                
                # 一つでも例外パターンに一致しないものがあれば削除
                if not all_match_exception and decorated_texts:
                    await self.delete_and_warn(message, "スポイラー")
                    self.logger.info(f"スポイラーが含まれるメッセージを削除しました - サーバー: {message.guild.id}, チャンネル: {message.channel.id}, ユーザー: {message.author.id}")
                    return
        except Exception as e:
            self.logger.error(f"メッセージ処理中にエラーが発生しました: {e}")
    
    async def delete_and_warn(self, message, decoration_type):
        """
        メッセージを削除し、警告を送信する関数
        """
        try:
            await message.delete()
            # 警告メッセージの内容
            warning = f"{decoration_type}（`{self.get_decoration_symbol(decoration_type)}`）を使った装飾はこのサーバーでは禁止されています。異議、顔文字申請はチケットからお願いします。"
            
            # サーバーの中でのみ機能させる（DMでは機能しない）
            if isinstance(message.channel, discord.TextChannel):
                # ユーザーにメンションして警告
                warning_msg = await message.channel.send(f"{message.author.mention} {warning}")
                # 数秒後にメッセージを削除
                await asyncio.sleep(10)
                try:
                    await warning_msg.delete()
                except discord.NotFound:
                    pass  # メッセージが既に削除されている場合
        except discord.Forbidden:
            self.logger.warning(f"メッセージの削除権限がありません - サーバー: {message.guild.id}, チャンネル: {message.channel.id}")
        except Exception as e:
            self.logger.error(f"メッセージの削除・警告中にエラーが発生しました: {e}")
    
    def get_decoration_symbol(self, decoration_type):
        """
        装飾タイプに応じたシンボルを返す
        """
        if decoration_type == "取り消し線":
            return "~~"
        elif decoration_type == "スポイラー":
            return "||"
        return ""

    # 管理者権限チェック
    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """管理者権限を持っているかチェック"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("このコマンドは管理者のみが使用できます。", ephemeral=True)
            return False
        return True

    # スラッシュコマンドグループの定義
    decoration_group = app_commands.Group(name="decoration", description="装飾に関する設定コマンド")
    
    @decoration_group.command(name="add_exception", description="装飾の例外パターンを追加します")
    @app_commands.describe(
        decoration_type="装飾タイプ",
        pattern="例外として許可するパターン"
    )
    @app_commands.choices(decoration_type=[
        app_commands.Choice(name="取り消し線", value="strikethrough"),
        app_commands.Choice(name="スポイラー", value="spoiler")
    ])
    async def add_exception(self, interaction: discord.Interaction, decoration_type: str, pattern: str):
        """例外パターンを追加するコマンド"""
        # 管理者権限チェック
        if not await self.is_admin(interaction):
            return
        
        try:
            # 例外パターンを追加
            if pattern not in self.exceptions[decoration_type]:
                self.exceptions[decoration_type].append(pattern)
                # ファイルに保存
                self.save_exceptions()
                
                decoration_name = "取り消し線" if decoration_type == "strikethrough" else "スポイラー"
                await interaction.response.send_message(f"{decoration_name}の例外パターン「{pattern}」を追加しました。", ephemeral=True)
                
                self.logger.info(f"{decoration_name}の例外パターンが追加されました - サーバー: {interaction.guild_id}, 管理者: {interaction.user.id}, パターン: {pattern}")
            else:
                await interaction.response.send_message("そのパターンは既に登録されています。", ephemeral=True)
        except Exception as e:
            self.logger.error(f"例外パターン追加中にエラーが発生しました: {e}")
            await interaction.response.send_message("エラーが発生しました。管理者に連絡してください。", ephemeral=True)

    @decoration_group.command(name="remove_exception", description="装飾の例外パターンを削除します")
    @app_commands.describe(
        decoration_type="装飾タイプ",
        pattern="削除する例外パターン"
    )
    @app_commands.choices(decoration_type=[
        app_commands.Choice(name="取り消し線", value="strikethrough"),
        app_commands.Choice(name="スポイラー", value="spoiler")
    ])
    async def remove_exception(self, interaction: discord.Interaction, decoration_type: str, pattern: str):
        """例外パターンを削除するコマンド"""
        # 管理者権限チェック
        if not await self.is_admin(interaction):
            return
        
        try:
            # 例外パターンを削除
            if pattern in self.exceptions[decoration_type]:
                self.exceptions[decoration_type].remove(pattern)
                # ファイルに保存
                self.save_exceptions()
                
                decoration_name = "取り消し線" if decoration_type == "strikethrough" else "スポイラー"
                await interaction.response.send_message(f"{decoration_name}の例外パターン「{pattern}」を削除しました。", ephemeral=True)
                
                self.logger.info(f"{decoration_name}の例外パターンが削除されました - サーバー: {interaction.guild_id}, 管理者: {interaction.user.id}, パターン: {pattern}")
            else:
                await interaction.response.send_message("そのパターンは登録されていません。", ephemeral=True)
        except Exception as e:
            self.logger.error(f"例外パターン削除中にエラーが発生しました: {e}")
            await interaction.response.send_message("エラーが発生しました。管理者に連絡してください。", ephemeral=True)

    @decoration_group.command(name="list_exceptions", description="装飾の例外パターンの一覧を表示します")
    @app_commands.describe(
        decoration_type="表示する装飾タイプ"
    )
    @app_commands.choices(decoration_type=[
        app_commands.Choice(name="取り消し線", value="strikethrough"),
        app_commands.Choice(name="スポイラー", value="spoiler"),
        app_commands.Choice(name="全て", value="all")
    ])
    async def list_exceptions(self, interaction: discord.Interaction, decoration_type: str = "all"):
        """例外パターンの一覧を表示するコマンド"""
        # 管理者権限チェック
        if not await self.is_admin(interaction):
            return
        
        try:
            if decoration_type == "all":
                # 全ての例外パターン一覧を表示
                embed = discord.Embed(title="例外パターン一覧", color=discord.Color.blue())
                
                strikethrough_patterns = "\n".join(self.exceptions["strikethrough"]) if self.exceptions["strikethrough"] else "なし"
                spoiler_patterns = "\n".join(self.exceptions["spoiler"]) if self.exceptions["spoiler"] else "なし"
                
                embed.add_field(name="取り消し線の例外", value=strikethrough_patterns, inline=False)
                embed.add_field(name="スポイラーの例外", value=spoiler_patterns, inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                # 指定された装飾タイプの例外パターン一覧を表示
                decoration_name = "取り消し線" if decoration_type == "strikethrough" else "スポイラー"
                embed = discord.Embed(title=f"{decoration_name}の例外パターン一覧", color=discord.Color.blue())
                
                patterns = "\n".join(self.exceptions[decoration_type]) if self.exceptions[decoration_type] else "なし"
                embed.description = patterns
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            self.logger.debug(f"例外パターン一覧を表示しました - サーバー: {interaction.guild_id}, 管理者: {interaction.user.id}, タイプ: {decoration_type}")
        except Exception as e:
            self.logger.error(f"例外パターン一覧表示中にエラーが発生しました: {e}")
            await interaction.response.send_message("エラーが発生しました。管理者に連絡してください。", ephemeral=True)

async def setup(bot):
    """Cogをボットに追加する関数"""
    await bot.add_cog(ModerationCog(bot))
import json
import os
import logging
from typing import Dict, Any, Optional

class ConfigManager:
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.logger = logging.getLogger('bot.configmanager')
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """設定ファイルを読み込む"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    'guilds': {},
                    'global': {
                        'log_channels': {},
                        'vc_log_channels': {},
                        'photo_archive_channel': None,  # グローバル設定に移動
                        'banned_words': [],
                        'spam_settings': {
                            'message_count': 5,
                            'time_window': 5,
                            'action': 'timeout',
                            'timeout_duration': 300
                        }
                    }
                }
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {'guilds': {}, 'global': {}}

    def set_archive_channel(self, channel_id: int) -> bool:
        """アーカイブチャンネルをグローバルに設定"""
        try:
            if 'global' not in self.config:
                self.config['global'] = {}
            
            self.config['global']['photo_archive_channel'] = channel_id
            return self._save_config()
        except Exception as e:
            self.logger.error(f"Error setting archive channel: {e}")
            return False

    def get_archive_channel(self) -> Optional[int]:
        """グローバルアーカイブチャンネルのIDを取得"""
        return self.config.get('global', {}).get('photo_archive_channel')


    def _save_config(self) -> bool:
        """設定をファイルに保存する"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False

    def has_guild(self, guild_id: str) -> bool:
        """ギルドの設定が存在するか確認"""
        return guild_id in self.config.get('guilds', {})

    def initialize_guild(self, guild_id: str) -> None:
        """ギルドの初期設定を作成"""
        if 'guilds' not in self.config:
            self.config['guilds'] = {}
        
        if guild_id not in self.config['guilds']:
            self.config['guilds'][guild_id] = {
                'photo_archive_channel': None,
                'log_channel': None,
                'vc_log_channel': None,
                'mod_log_channel': None,
                'banned_words': [],
                'spam_settings': {
                    'message_count': 5,
                    'time_window': 5,
                    'action': 'timeout',
                    'timeout_duration': 300
                }
            }
            self._save_config()

    def get_guild_config(self, guild_id: str) -> Optional[dict]:
        """ギルドの設定を取得"""
        return self.config.get('guilds', {}).get(guild_id)

    def update_guild_config(self, guild_id: str, updates: Dict[str, Any]) -> bool:
        """
        ギルドの設定を更新
        
        Parameters
        ----------
        guild_id : str
            ギルドID
        updates : Dict[str, Any]
            更新する設定のキーと値
        
        Returns
        -------
        bool
            更新の成功/失敗
        """
        try:
            if not self.has_guild(guild_id):
                self.initialize_guild(guild_id)
            
            for key, value in updates.items():
                self.config['guilds'][guild_id][key] = value
            
            return self._save_config()
        except Exception as e:
            self.logger.error(f"Error updating guild config: {e}")
            return False

    def get_global_config(self) -> dict:
        """グローバル設定を取得"""
        return self.config.get('global', {})

    def update_global_config(self, updates: Dict[str, Any]) -> bool:
        """グローバル設定を更新"""
        try:
            if 'global' not in self.config:
                self.config['global'] = {}
            
            for key, value in updates.items():
                self.config['global'][key] = value
            
            return self._save_config()
        except Exception as e:
            self.logger.error(f"Error updating global config: {e}")
            return False
    
    def get_default_settings(self) -> dict:
        return {
            'spam_settings': {
                'message_count': 5,
                'time_window': 5,
                'action': 'timeout',
                'timeout_duration': 300
            }
        }            

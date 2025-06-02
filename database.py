import sqlite3
import datetime
import asyncio

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot_statistics.db')
        self.cursor = self.conn.cursor()
        self.init_database()
    
    def init_database(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_stats (
                guild_id INTEGER,
                user_id INTEGER,
                date TEXT,
                message_count INTEGER,
                PRIMARY KEY (guild_id, user_id, date)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS voice_stats (
                guild_id INTEGER,
                user_id INTEGER,
                date TEXT,
                voice_time INTEGER,
                PRIMARY KEY (guild_id, user_id, date)
            )
        ''')
        
        self.conn.commit()
    
    def save_message_stats(self, guild_id, user_id, message_count):
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        self.cursor.execute('''
            INSERT OR REPLACE INTO message_stats (guild_id, user_id, date, message_count)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, today, message_count))
        self.conn.commit()
    
    async def close(self):
        # async メソッドにする
        if hasattr(self, 'conn') and self.conn is not None:
            self.conn.close()
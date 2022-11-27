import hashlib
import mysql.connector as db
import os
from random import randint
from socket import gethostname

from modules import config
from modules.logger.base import createLogger
from .base import Writer

class DatabaseWriter(Writer):
    def __init__(self, config: config.ConfigHandler, video_id: str):
        super().__init__(config, video_id)

        self.conn = db.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_database
        )
        self.cursor = self.conn.cursor()
        if video_id:
            self.shard = str(int(hashlib.sha1(video_id.encode()).hexdigest()[:8], 16) % config.db_nshards)
        self.db_table = config.db_table
        self.db_stream_table = config.db_stream_table

        self.chat_buffer = []
        self.threads = []

        self.hostname = gethostname() # for logging in db

        self.next_batch = randint(30, 100)

    def validate_configs(self, config: config.ConfigHandler):
        required_attrs = ["db_host", "db_port", "db_user", "db_password", "db_database", "db_table", "db_stream_table", "db_nshards"]
        
        for attr in required_attrs:
            if not hasattr(config, attr) or getattr(config, attr) is None:
                self.logger.error(f"{attr} missing")
                return False

        return True

    @staticmethod
    def check_config_enabled(config: config.ConfigHandler):
        if not hasattr(config, 'write_to_db'):
            self.logger.warning("config has no attribute for DatabaseWriter")
            return False
        
        return config.write_to_db

    def generate_batch(self):
        self.next_batch = randint(30,100)

    def process(self, chat):
        self.chat_buffer.append((
            self.video_id,
            chat.id.replace('%3D', '='),
            chat.message,
            str(chat.timestamp),
            chat.author.name,
            chat.author.channelId,
            self.hostname
            ))

        if len(self.chat_buffer) >= self.next_batch:
            self.post()
            self.chat_buffer = []
            self.generate_batch()

    def process_stream(self, stream):
        try:
            self.cursor.execute(r'REPLACE INTO stream_tab(id, title, topic_id,  channel_id, channel_name) VALUES(%s, %s, %s, %s, %s)',
                    (stream['id'], stream['title'], stream.get('topic_id', None), stream['channel']['id'], stream['channel']['name']))
            self.conn.commit()
        except Exception as e:
            self.logger.error(str(e))

    def post(self):
        self.logger.info(f"posting {self.next_batch} chats...")
        print(f"posting {self.next_batch} chats...")
        try:
            query = r'INSERT INTO ' + self.db_table + '_' + self.shard + r' VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE source = CONCAT(source, ' + f"' {self.hostname}\')"
            self.cursor.executemany(query, self.chat_buffer)
            self.conn.commit()
        except Exception as e:
            self.logger.error(str(e))
        self.logger.info("done")
        print("done")

    def finalise(self):
        self.post()
        self.cursor.close()
        self.conn.close()

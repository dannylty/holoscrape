import hashlib
import logging
import mysql.connector as db
import os
from socket import gethostname

from modules import config
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
        self.nshards = config.db_nshards
        self.db_table = config.db_table
        self.db_stream_table = config.db_stream_table

        self.chat_buffer = []
        self.threads = []

        self.hostname = gethostname() # for logging in db
        
    def validate_configs(self, config: config.ConfigHandler):
        required_attrs = ["db_host", "db_port", "db_user", "db_password", "db_database", "db_table", "db_stream_table", "db_nshards"]
        
        for attr in required_attrs:
            if not hasattr(config, attr) or getattr(config, attr) is None:
                logging.error(f"{attr} missing")
                return False

        return True

    @staticmethod
    def check_config_enabled(config: config.ConfigHandler):
        if not hasattr(config, 'write_to_db'):
            logging.warning('config has no attribute for DatabaseWriter')
            return False
        
        return config.write_to_local

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

        if len(self.chat_buffer) >= 100:
            self.post()
            self.chat_buffer = []

    def process_stream(self, stream):
        try:
            self.cursor.execute(r'REPLACE INTO stream_tab(id, title, topic_id,  channel_id, channel_name) VALUES(%s, %s, %s, %s, %s)',
                    (stream['id'], stream['title'], stream.get('topic_id', None), stream['channel']['id'], stream['channel']['name']))
            self.conn.commit()
        except Exception as e:
            logging.error(str(e))

    def get_shard(self):
        return str(int(hashlib.sha1(self.video_id).hexdigest()[:8], 16) % self.nshards)

    def post(self):
        print("start post")
        try:
            query = r'INSERT INTO ' + self.db_table + '_' + self.get_shard() + r' VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE source = CONCAT(source, ' + f"' {self.hostname}\')"
            self.cursor.executemany(query, self.chat_buffer)
            self.conn.commit()
        except Exception as e:
            logging.error(str(e))
        print("end post")

    def finalise(self):
        self.post()
        self.cursor.close()
        self.conn.close()

import logging
import mysql.connector as db
import os
from random import randint
from socket import gethostname
import threading

import config
from .base import Writer

class DatabaseWriter(Writer):
    def __init__(self, config: config.ConfigHandler, video_id: str):
        super().__init__(config, video_id)

        self.lock = threading.Lock()
        self.conn = db.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_database
        )
        self.cursor = self.conn.cursor()
        self.nshards = config.db_nshards
        self.shard_pointer = randint(0, config.db_nshards - 1)
        self.db_table = config.db_table

        self.chat_buffer = []
        self.threads = []

        self.hostname = gethostname() # for logging in db
        
    def validate_configs(self, config: config.ConfigHandler):
        required_attrs = ["db_host", "db_port", "db_user", "db_password", "db_database", "db_table", "db_nshards"]
        
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

    def advance_shard_pointer(self):
        self.shard_pointer = (self.shard_pointer + 1) % self.nshards

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

        if len(self.chat_buffer) >= 10:
            self.lock.acquire()
            t = threading.Thread(target=self.post)
            t.start()
            self.threads.append(t)
            self.lock.release() # probably race condition on shard pointer but who cares
            self.advance_shard_pointer()
            if len(self.threads) > 3:
                self.threads.pop(0).join()

    def post(self):
        self.lock.acquire()
        try:
            query = r'INSERT IGNORE INTO ' + self.db_table + '_' + str(self.shard_pointer) + r' VALUES (%s, %s, %s, %s, %s, %s, %s)'
            self.cursor.executemany(query, self.chat_buffer)
            self.conn.commit()
        except Exception as e:
            logging.error(str(e))
        
        self.lock.release()


    def finalise(self):
        self.post()
        self.cursor.close()
        self.conn.close()
import json
import os

class ConfigHandler:
    def __init__(self, json_file_path: str):
        self.parse_json(json_file_path)
        self.holodex_apikey = os.getenv('HOLODEX_API_KEY')

    def parse_json(self, json_file_path):
        with open(json_file_path, 'r') as f:
            data = json.load(f)

            self.write_to_db = data['write_to_db']
            if self.write_to_db:
                self.db_host = data['db_host']
                self.db_port = data['db_port']
                self.db_user = data['db_user']
                self.db_password = data['db_password']
                self.db_database = data['db_database']
                self.db_table = data['db_table']
                self.db_stream_table = data['db_stream_table']
                self.db_nshards = data['db_nshards']

            self.write_to_local = data['write_to_local']
            self.local_path = data['local_path']
            self.log_path = data['log_path']

def get_configs() -> ConfigHandler:
    return ConfigHandler("config.json")
    

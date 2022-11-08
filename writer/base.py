import config

class Writer:
    def __init__(self, config: config.ConfigHandler, video_id: str):
        if not self.validate_configs(config):
            raise Exception()

        self.video_id = video_id

    def validate_configs(self, config: config.ConfigHandler):
        return True

    @staticmethod    
    def check_config_enabled(config: config.ConfigHandler):
        pass

    def process(self, chats):
        pass

    def finalise(self):
        pass
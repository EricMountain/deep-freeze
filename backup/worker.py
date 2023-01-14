from .backup import BackupProcessor
from db import Database


class Worker():
    def __init__(self):
        self.db = Database()

    def run(self):
        client_configs = self.db.get_active_client_configs()
        for cc in client_configs:
            print(f"{cc}")
            BackupProcessor(self.db, cc).run()

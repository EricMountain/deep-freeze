from .backup import Backup
from db import Database, ClientConfigFactory


class Coordinator():
    def __init__(self):
        self.db = Database()

    def run(self):
        ccf = ClientConfigFactory(self.db)
        client_configs = ccf.get_active_client_configs()
        for cc in client_configs:
            print(f"{cc}")
            Backup(self.db, cc).run()

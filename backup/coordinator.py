from db import Database, ClientConfigFactory, ClientConfig

from .backup import Backup
from .purge import Purge


class Coordinator():
    def __init__(self):
        self.db = Database()

    def run(self):
        ccf = ClientConfigFactory(self.db)
        client_configs = ccf.get_active_client_configs()
        for cc in client_configs:
            if cc.options[ClientConfig.MANUAL_ONLY] == ClientConfig.YES:
                continue
            print(f"Backing up: {cc}")
            Backup(self.db, cc).run()
            print(f"Purging obsolete archives: {cc}")
            Purge(self.db, cc).run()

    def run_manual(self, cloud_provider, region, client_name, backup_root):
        ccf = ClientConfigFactory(self.db)
        client_configs = ccf.get_active_client_configs()
        for cc in client_configs:
            if cc.cloud != cloud_provider:
                print(f"Skipping (cloud): {cc}")
                continue
            if cc.region != region:
                print(f"Skipping (region): {cc}")
                continue
            if cc.client_fqdn != client_name:
                print(f"Skipping (client): {cc}")
                continue
            if cc.backup_root != backup_root:
                print(f"Skipping (root = {backup_root}): {cc}")
                continue
            print(f"Backing up: {cc}")
            Backup(self.db, cc).run()
            print(f"Purging obsolete archives: {cc}")
            Purge(self.db, cc).run()

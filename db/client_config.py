import os
import re

from dataclasses import dataclass
from typing import Dict
from typing import List

from .db import Database


@dataclass
class ClientConfig():
    cloud: str
    region: str
    credentials: str
    bucket: str
    client_fqdn: str
    backup_root: str
    key_file_path: str
    options: Dict[str, str]
    exclusions: List[re.Pattern]
    db: Database

    BACKUPS_CROSS_DEVICES = "backups_cross_devices"
    MANUAL_ONLY = "manual_only"
    TMP_DIR = "temporary_directory"
    YES = "Y"
    NO = "N"

    def add_to_database(self):
        self.add_backup_client_config()

    def add_backup_client_config(self):
        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  insert into backup_client_configs(client_fqdn, backup_root, status, key_file_path,
                                                      cloud, region, credentials, bucket)
                  values(?,?,?,?,?,?,?,?)
                  '''
            cursor.execute(query, (self.client_fqdn, self.backup_root, "active", self.key_file_path,
                                   self.cloud, self.region, self.credentials, self.bucket))

            for key, value in self.options.items():
                query = '''
                        insert into backup_client_configs_options(client_fqdn, backup_root, key, value)
                        values(?,?,?,?)
                        '''
                cursor.execute(
                    query, (self.client_fqdn, self.backup_root, key, value))

    def is_excluded(self, root: str, path: str) -> bool:
        if self.exclusions is None or len(self.exclusions) == 0:
            return False

        if root == "":
            root = "/"
        fullpath = os.path.join(root, path)

        for exclusion in self.exclusions:
            if exclusion.fullmatch(fullpath):
                return True

        return False


@dataclass
class ClientConfigFactory():
    db: Database

    def get_active_client_configs(self):
        configs = []
        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  select cloud, region, credentials, bucket, client_fqdn, backup_root, key_file_path
                  from backup_client_configs
                  where status = 'active'
                  '''
            cursor.execute(query)

            deep_freeze_root = os.path.dirname(self.db.db_path)
            deep_freeze_root_bkp_config = None
            for row in cursor:
                cursor2 = self.db.connection.cursor()
                query = '''
                        select key, value
                        from backup_client_configs_options
                        where client_fqdn = ?
                        and backup_root = ?
                        '''
                cursor2.execute(
                    query, (row["client_fqdn"], row["backup_root"]))
                options = {}
                for row2 in cursor2:
                    options[row2["key"]] = row2["value"]

                cursor3 = self.db.connection.cursor()
                query = '''
                        select pattern
                        from backup_client_configs_exclusions
                        where client_fqdn = ?
                        and backup_root = ?
                        '''
                cursor3.execute(
                    query, (row["client_fqdn"], row["backup_root"]))

                exclusions = []
                for row3 in cursor3:
                    exclusions.append(re.compile(row3["pattern"]))

                if ClientConfig.MANUAL_ONLY not in options:
                    options[ClientConfig.MANUAL_ONLY] = ClientConfig.NO

                cc = ClientConfig(row["cloud"], row["region"], row["credentials"], row["bucket"],
                                  row["client_fqdn"], row["backup_root"], row["key_file_path"],
                                  options, exclusions, self.db)
                if cc.backup_root == deep_freeze_root:
                    deep_freeze_root_bkp_config = cc
                    continue
                configs.append(cc)

            if deep_freeze_root_bkp_config is not None:
                configs.append(deep_freeze_root_bkp_config)

        return configs

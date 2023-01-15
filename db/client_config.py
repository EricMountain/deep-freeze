from dataclasses import dataclass

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
    db: Database

    def add_to_database(self):
        self.add_backup_client_config(self.client_fqdn, self.backup_root, self.key_file_path,
                                      self.cloud, self.region, self.credentials, self.bucket)

    def add_backup_client_config(self, client_fqdn: str, backup_root: str, key_file_path: str,
                                 cloud: str, region: str, credentials: str, bucket: str):
        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  insert into backup_client_configs(client_fqdn, backup_root, status, key_file_path,
                                                      cloud, region, credentials, bucket)
                  values(?,?,?,?,?,?,?,?)
                  '''
            cursor.execute(query, (client_fqdn, backup_root, "active", key_file_path,
                                   cloud, region, credentials, bucket))

@dataclass
class ClientConfigFactory():
    db: Database

    def get_active_client_configs(self):
        entries = []
        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  select cloud, region, credentials, bucket, client_fqdn, backup_root, key_file_path
                  from backup_client_configs
                  where status = 'active'
                  '''
            cursor.execute(query)

            for row in cursor:
                entries.append(ClientConfig(row["cloud"], row["region"], row["credentials"], row["bucket"],
                                            row["client_fqdn"], row["backup_root"], row["key_file_path"],
                                            self.db))

        return entries

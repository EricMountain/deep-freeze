import sqlite3

from dataclasses import dataclass

from .schema_upgrade import SchemaUpgrade


@dataclass()
class SchemaUpgradeV1(SchemaUpgrade):
    connection: sqlite3.Connection
    schema_version: int = 1

    def __post_init__(self):
        self.upgrade()
        self.set_version()

    def upgrade(self):
        self.ddl_create_table_backup_client_configs_options()

    def ddl_create_table_backup_client_configs_options(self):
        self.connection.execute('''create table if not exists backup_client_configs_options (
                                 option_id primary key,
                                 client_fqdn text not null,
                                 backup_root text not null,
                                 key text not null,
                                 value text,
                                 foreign key (client_fqdn, backup_root) references backup_client_configs (client_fqdn, backup_root)
                                 )
                              ''')
        self.connection.execute('''create unique index if not exists backup_client_configs_options_1 on backup_client_configs_options (
                                 client_fqdn,
                                 backup_root,
                                 key
                                 )
                              ''')
        self.connection.execute('''insert into backup_client_configs_options(client_fqdn, backup_root, key, value)
                                   select client_fqdn, backup_root, 'backups_cross_devices', 'Y'
                                   from backup_client_configs
                              ''')

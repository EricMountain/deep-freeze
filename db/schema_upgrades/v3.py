import sqlite3

from dataclasses import dataclass

from .schema_upgrade import SchemaUpgrade


@dataclass()
class SchemaUpgradeV3(SchemaUpgrade):
    connection: sqlite3.Connection
    schema_version: int = 3

    def __post_init__(self):
        self.upgrade()
        self.set_version()

    def upgrade(self):
        self.ddl_create_table_exclusions()

    def ddl_create_table_exclusions(self):
        self.connection.execute('''create table if not exists backup_client_configs_exclusions (
                                 client_fqdn text not null,
                                 backup_root text not null,
                                 pattern text not null,
                                 primary key (client_fqdn, backup_root, pattern)
                                 )
                              ''')

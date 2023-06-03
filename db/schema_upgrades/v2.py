import sqlite3

from dataclasses import dataclass

from .schema_upgrade import SchemaUpgrade


@dataclass()
class SchemaUpgradeV2(SchemaUpgrade):
    connection: sqlite3.Connection
    schema_version: int = 2

    def __post_init__(self):
        self.upgrade()
        self.set_version()

    def upgrade(self):
        self.connection.execute('''create index if not exists file_archive_records_1 on file_archive_records (archive_id)
                              ''')

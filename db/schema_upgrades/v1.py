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
        pass

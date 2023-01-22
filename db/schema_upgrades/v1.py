import sqlite3

from dataclasses import dataclass


@dataclass()
class SchemaUpgradeV1():
    connection: sqlite3.Connection
    schema_version: int = 1

    def __post_init__(self):
        self.set_version()

    def set_version(self):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update deep_freeze_metadata
                  set value = ?
                  where key = 'schema_version'
                  '''
            cursor.execute(query, (str(self.schema_version),))

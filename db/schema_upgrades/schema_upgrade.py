import sqlite3

from dataclasses import dataclass


@dataclass()
class SchemaUpgrade():
    connection: sqlite3.Connection
    schema_version: int

    def set_version(self):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update deep_freeze_metadata
                  set value = ?
                  where key = 'schema_version'
                  '''
            cursor.execute(query, (str(self.schema_version),))

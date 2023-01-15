import os
import time

from dataclasses import dataclass

from .db import Database
from .client_config import ClientConfig


@dataclass
class File():
    db: Database
    client_config: ClientConfig
    root: str
    file: str

    def __post_init__(self):
        abs_path = os.path.join(self.root, self.file)
        self.metadata = os.lstat(abs_path)

        # Trim root and trailing slash
        self.rel_path = abs_path[len(self.client_config.backup_root) + 1:]

    def upsert(self):
        datetime_str = self._epoch2fmt(self.metadata.st_mtime)

        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  insert into files(client_fqdn, backup_root, relative_path, size, modification, status, sweep_mark,
                                    force_backup, new_size, new_modification, new_status)
                  values(?,?,?,?,?,'present','present','Y',?,?,'present')
                  on conflict(client_fqdn, backup_root, relative_path) do
                  update set
                     new_size = ?,
                     new_modification = ?,
                     new_status = 'present',
                     sweep_mark = 'present'
                  '''
            cursor.execute(query, (self.client_config.client_fqdn, self.client_config.backup_root,
                                   self.rel_path, self.metadata.st_size,
                                   datetime_str,
                                   self.metadata.st_size, datetime_str,
                                   self.metadata.st_size, datetime_str))

    def _epoch2fmt(self, epoch) -> str:
        return time.strftime('%Y-%m-%d %H:%M:%S %Z', time.gmtime(epoch))

import os
import subprocess
import time
import tarfile
import tempfile

from dataclasses import dataclass

from db import Database, ClientConfig, File


@dataclass
class Purge():
    """
    Deletes obsolete archives.
    """

    db: Database
    client_config: ClientConfig

    def run(self):
        self.fix_stats()
        self.purge()

    def fix_stats(self):
        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  update s3_archives as s3
                  set relevant_size = (select ifnull(sum(file_size), 0) from file_archive_records as far where far.archive_id = s3.archive_id and far.status = 'uploaded')
                  '''
            cursor.execute(query)

    def purge(self):
        self.db.flag_archives_to_delete(self.client_config.cloud, self.client_config.region,
                                        self.client_config.bucket, self.client_config.backup_root)
        archives = self.db.get_archives_pending_deletion(self.client_config.cloud, self.client_config.region,
                                                    self.client_config.bucket, self.client_config.backup_root)
        for archive in archives:
            cmd = f"aws --profile {self.client_config.credentials}"
            cmd += f" s3 rm"
            cmd += f" s3://{self.client_config.bucket}/{archive['archive_file_name']}.enc"
            completed = subprocess.run(cmd.split())
            
            if completed.returncode == 0:
                self.db.flag_archive_deleted(archive['archive_id'])
        
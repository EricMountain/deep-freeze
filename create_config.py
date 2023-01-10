#!/usr/bin/env python3

from db import Database, ClientConfig

class Worker():
    def __init__(self):
        self.db = Database()

    def run(self):
        self.db.add_backup_client_config("host", "path_to_backup", "symmetric_encryption_key_file_path",
                                            "aws", "region", "user/profile", "bucket")


w = Worker()
w.run()

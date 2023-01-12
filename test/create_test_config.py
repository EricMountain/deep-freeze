#!/usr/bin/env python3

from db import Database

class Worker():
    def __init__(self):
        self.db = Database()

    def run(self):
        self.db.add_backup_client_config("host", "/deep-freeze/test/root", "/deep-freeze/test/key",
                                            "aws", "region", "user/profile", "bucket")


w = Worker()
w.run()

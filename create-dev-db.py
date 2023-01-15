#!/usr/bin/env python3

from db import Database, ClientConfig

class Worker():
    def __init__(self):
        self.db = Database()

    def run(self):
        print("DB created")


w = Worker()
w.run()

#!/usr/bin/env python3

from datetime import datetime, timezone
import time

from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt

from db import Database, ClientConfigFactory, ClientConfig


@dataclass
class Report():
    db: Database
    client_config: ClientConfig

    def run(self):
        np.set_printoptions(precision=2)
        values = []
        rows = self.db.decide_archives_to_delete(self.client_config.cloud, self.client_config.region,
                                                self.client_config.bucket, self.client_config.backup_root)
        not_relevant_count = 0
        for row in rows:
            arch_name = row['archive_file_name']
            id = row['archive_id']
            relevant = row['relevant_size']
            total = row['total_size']
            status = row['status']
            created = row['created']

            parser_dt = datetime.now(timezone.utc)
            created_dt = parser_dt.strptime(created, "%Y-%m-%d %H:%M:%S")

            now_dt = datetime.utcnow()
            age_dt = now_dt - created_dt
            if relevant == 0:
                print(
                    f"{arch_name} ({id}) No longer relevant, age: {age_dt}")
                values.append(0)
                not_relevant_count += 1
            elif relevant != total:
                pct = relevant * 100 / total
                print(
                    f"{arch_name} ({id}) {pct:.2f}% relevant ({relevant}/{total}), age: {age_dt}")
                values.append(pct)
            else:
                print(f"{arch_name} ({id}) 100% relevant ({relevant}/{total}), age: {age_dt}")
                values.append(100.0)

        print(f"Total non-relevant files: {not_relevant_count}")
        hist, bin_edges = np.histogram(values)
        print(f"{hist}")
        print(f"{bin_edges}")

        plt.hist(values, bins=10)
        # plt.show()


class ReportAll():
    def __init__(self):
        self.db = Database()

    def run(self):
        ccf = ClientConfigFactory(self.db)
        client_configs = ccf.get_active_client_configs()
        for cc in client_configs:
            print(f"{cc}")
            Report(self.db, cc).run()


ReportAll().run()

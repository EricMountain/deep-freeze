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

    def fix_stats(self):
        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  update s3_archives as s3
                  set relevant_size = (select ifnull(sum(file_size), 0) from file_archive_records as far where far.archive_id = s3.archive_id and far.status = 'uploaded')
                  '''
            cursor.execute(query)

    def run(self):
        self.fix_stats()

        np.set_printoptions(precision=2)
        values = []

        with self.db.connection:
            cursor = self.db.connection.cursor()
            query = '''
                  select s3.archive_file_name, s3.total_size, s3.relevant_size, s3.status, s3.archive_id, s3.created
                  from s3_archives as s3
                  inner join backup_client_configs as cc using (cloud, region, bucket)
                  where cc.cloud = ?
                  and cc.region = ?
                  and cc.bucket = ?
                  and cc.backup_root = ?
                  and s3.status = 'uploaded'
                  '''
            cursor.execute(query, (self.client_config.cloud, self.client_config.region,
                                   self.client_config.bucket, self.client_config.backup_root))

            for row in cursor:
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
                        f"No longer relevant: {arch_name} {age_dt}")
                    values.append(0)
                elif relevant != total:
                    pct = relevant * 100 / total
                    print(
                        f"{arch_name} ({id}) {pct:.2f}% relevant ({relevant}/{total})")
                    values.append(pct)
                # else:
                #     values.append(100.0)

        hist, bin_edges = np.histogram(values)
        print(f"{hist}")
        print(f"{bin_edges}")

        plt.hist(values, bins=10)
        plt.show()


class ReportAll():
    def __init__(self):
        self.db = Database()

    def run(self):
        ccf = ClientConfigFactory(self.db)
        client_configs = ccf.get_active_client_configs()
        for cc in client_configs:
            print(f"{cc}")
            Report(self.db, cc).run()
            break


ReportAll().run()

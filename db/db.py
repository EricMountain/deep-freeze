import sqlite3
import os
import time

from dataclasses import dataclass

from .ddl import MaintainSchema


@dataclass
class Database():

    def __post_init__(self):
        # TODO check sanity
        home = os.getenv('HOME')
        rcdir = '.deep-freeze-backups'
        # TODO create directory if it does not exist
        self.db_path = os.path.join(home, rcdir, "deep-freeze-backups.db")
        # self.db_path = "deep-freeze-dev.db"

        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

        MaintainSchema(self.connection)

        self._fix_stats()

    # TODO: see if/when we can remove this (is the bug still present, has this run on all clients?)
    # Could be moved to a schema upgrade step
    def _fix_stats(self):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update s3_archives as s3
                  set relevant_size = (select ifnull(sum(file_size), 0) from file_archive_records as far where far.archive_id = s3.archive_id and far.status = 'uploaded')
                  '''
            cursor.execute(query)

    def set_sweep_mark(self, client_fqdn, backup_root):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update files
                  set sweep_mark = 'absent'
                  where client_fqdn = ?
                  and backup_root = ?
                  '''
            cursor.execute(query, (client_fqdn, backup_root))

    def update_deleted_files_new_status(self, client_fqdn, backup_root):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update files
                  set new_status = 'absent'
                  where client_fqdn = ?
                  and backup_root = ?
                  and sweep_mark = 'absent'
                  '''
            cursor.execute(query, (client_fqdn, backup_root))

        # Get the ids of archives that contained the previous "last backup" of files
        # that have been deleted, and the space occupied by those files
        entries = []
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select sum(f.size) size, f.last_archive_id archive_id
                  from files f
                  where new_status = 'absent'
                  group by f.last_archive_id
                  '''
            cursor.execute(query)

            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

        self.update_superseded_archives(entries, None)

        # Flag previous file backup records as deleted
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update file_archive_records
                  set status = 'deleted'
                  where file_id in (select file_id
                                    from files
                                    where new_status = 'absent'
                                    and client_fqdn = ?
                                    and backup_root = ?)
                  '''
            cursor.execute(query, (client_fqdn, backup_root))

        # Update file sizes etc with the latest values
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update files
                  set status = new_status,
                     new_size = null,
                     new_modification = null,
                     new_status = null,
                     force_backup = 'N'
                  where new_status = 'absent'
                  '''
            cursor.execute(query)

    def update_superseded_archives(self, entries, new_archive_id: int):
        for entry in entries:
            # Remove superseded file size amounts from relevant size of previous archives
            with self.connection:
                cursor = self.connection.cursor()
                query = '''
                     update s3_archives
                     set relevant_size = relevant_size - ?
                     where archive_id = ?
                     '''
                cursor.execute(query, (entry["size"], entry["archive_id"]))

            # Flag previous file backup records as superseded
            if new_archive_id is not None:
                with self.connection:
                    cursor = self.connection.cursor()
                    query = '''
                        update file_archive_records
                        set status = 'superseded'
                        where status != 'superseded'
                        and file_id in (select file_id from file_archive_records where archive_id = ?)
                        and archive_id != ?
                        '''
                    cursor.execute(query, (new_archive_id, new_archive_id))

    def mark_files_for_backup(self, client_fqdn, backup_root):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update files
                  set force_backup = 'Y'
                  where client_fqdn = ?
                  and backup_root = ?
                  and sweep_mark = 'present'
                  and (new_size != size or new_modification != modification)
                  '''
            cursor.execute(query, (client_fqdn, backup_root))

    def get_files_to_backup(self, client_fqdn, backup_root) -> []:
        entries = []
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select relative_path, new_size, new_modification, file_id
                  from files
                  where client_fqdn = ?
                  and backup_root = ?
                  and force_backup = 'Y'
                  '''
            cursor.execute(query, (client_fqdn, backup_root))

            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

        return entries

    def new_archive(self, cloud: str, region: str, bucket: str, name: str) -> int:
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  insert into s3_archives(cloud, region, bucket, archive_file_name, total_size, relevant_size, status)
                  values(?,?,?,?,?,?,?)
                  '''
            cursor.execute(query, (cloud, region, bucket, name, 0, 0, "pending_upload"))

        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select archive_id
                  from s3_archives
                  where cloud = ?
                  and region = ?
                  and bucket = ?
                  and archive_file_name = ?
                  '''
            cursor.execute(query, (cloud, region, bucket, name))

            for row in cursor:
                return int(row["archive_id"])

    def archive_uploaded(self, archive_id: int, total_size: int):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update s3_archives
                  set status = 'uploaded',
                        total_size = ?,
                        relevant_size = ?
                  where archive_id = ?
                  '''
            cursor.execute(query, (total_size, total_size, archive_id))

        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update file_archive_records
                  set status = 'uploaded'
                  where archive_id = ?
                  '''
            cursor.execute(query, (archive_id,))

        # Get the ids of archives that contained the previous "last backup" of files
        # backed up in this archive, and the space occupied by those files
        entries = []
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select sum(f.size) size, f.last_archive_id archive_id
                  from files f inner join file_archive_records far on (f.file_id = far.file_id)
                  where far.archive_id = ?
                  group by f.last_archive_id
                  '''
            cursor.execute(query, (archive_id,))

            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

        self.update_superseded_archives(entries, archive_id)

        # Update file sizes etc with the latest values
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update files
                  set last_archive_id = ?,
                     size = new_size,
                     modification = new_modification,
                     status = new_status,
                     new_size = null,
                     new_modification = null,
                     new_status = null,
                     force_backup = 'N'
                  where file_id in (select file_id from file_archive_records where archive_id = ?)
                  '''
            cursor.execute(query, (archive_id, archive_id))

    def add_file_to_archive(self, archive_id: int, file_id: int, size: int, modification: str):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  insert into file_archive_records(file_id, archive_id, file_size, file_modification, status)
                  values(?,?,?,?,?)
                  '''
            cursor.execute(query, (file_id, archive_id, size, modification, "pending_upload"))

    def get_archives_to_delete(self, cloud: str, region: str, bucket: str, backup_root: str):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select s3.archive_file_name, s3.total_size, s3.relevant_size, s3.status, s3.archive_id, s3.created
                  from s3_archives as s3
                  inner join backup_client_configs as cc using (cloud, region, bucket)
                  where cc.cloud = ?
                  and cc.region = ?
                  and cc.bucket = ?
                  and cc.backup_root = ?
                  and s3.status = 'uploaded'
                  -- TODO: this will allow partially relevant archives to stick around longer
                  -- TODO: factor in the size relative to the target size
                  -- and julianday('now') - julianday(s3.created) > 180 + (s3.relevant_size / s3.total_size) * 180
                  -- TODO: remove this so we can handle partially relevant archives too
                  and s3.relevant_size = 0
                  and julianday('now') - julianday(s3.created) > 180
                  -- Ensures archives we're considering belong to the client_config
                  and s3.archive_id in (select distinct far.archive_id
                              from file_archive_records as far
                              inner join files as f using (file_id)
                              where far.archive_id = s3.archive_id
                              and f.client_fqdn = cc.client_fqdn
                              and f.backup_root = cc.backup_root)
                  '''
            cursor.execute(query, (cloud, region, bucket, backup_root))

            entries = []
            for row in cursor:
                entry = {}
                for col in row.keys():
                    entry[col] = row[col]
                entries.append(entry)

            return entries

    def flag_archive_to_delete(self, archive_id:int):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  update s3_archives
                  set status = 'pending_deletion'
                  where archive_id = ?
                  '''
            cursor.execute(query, (archive_id,))

    def flag_archives_to_delete(self, cloud: str, region: str, bucket: str, backup_root: str):
        rows = self.db.get_archives_to_delete(self.client_config.cloud, self.client_config.region,
                                                self.client_config.bucket, self.client_config.backup_root)
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
            pct = relevant * 100 / total
            print(f"Pending deletion: {arch_name} ({id}) {pct:.2f}% relevant ({relevant}/{total}), age: {age_dt}")
            self.flag_archive_to_delete(id)

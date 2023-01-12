import sqlite3
import os
import time

from dataclasses import dataclass


@dataclass
class ClientConfig():
    cloud: str
    region: str
    credentials: str
    bucket: str
    client_fqdn: str
    backup_root: str
    key_file_path: str


class Database():
    def __init__(self):
        # TODO check sanity
        home = os.getenv('HOME')
        rcdir = '.deep-freeze-backups'
        # TODO create directory if it does not exist
        self.db_path = os.path.join(home, rcdir, "deep-freeze-backups.db")
        # self.db_path = "deep-freeze-dev.db"

        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

        # Create base schema, aka version 0
        self.ddl_create_table_s3_archives()
        self.ddl_create_table_file_archive_records()
        self.ddl_create_table_files()
        self.ddl_create_table_backup_client_configs()
        self.ddl_create_table_deep_freeze_metadata()
        schema_version = self.get_schema_version()

    def get_schema_version(self) -> int:
        schema_version = ""
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select value
                  from deep_freeze_metadata
                  where key = 'schema_version'
                  '''
            cursor.execute(query)

            for row in cursor:
                schema_version = row["value"]
        if schema_version == "":
            schema_version = "0"
            self.connection.execute('''insert into deep_freeze_metadata(key, value)
                                    values('schema_version', '0')
                                 ''')

        return int(schema_version)

    def ddl_create_table_backup_client_configs(self):
        self.connection.execute('''create table if not exists backup_client_configs (
                                 cloud text not null,
                                 region text not null,
                                 bucket text not null,
                                 credentials text not null,
                                 client_fqdn text not null,
                                 backup_root text not null,
                                 status text not null,
                                 key_file_path not null,
                                 primary key (client_fqdn, backup_root)
                                 )
                              ''')

    def ddl_create_table_deep_freeze_metadata(self):
        self.connection.execute('''create table if not exists deep_freeze_metadata (
                                 key text not null primary key,
                                 value text not null
                                 )
                              ''')

    def ddl_create_table_files(self):
        self.connection.execute('''create table if not exists files (
                                 file_id integer primary key,
                                 client_fqdn text not null,
                                 backup_root text not null,
                                 relative_path text not null,
                                 size integer not null,
                                 modification datetime not null,
                                 status text not null,
                                 new_size integer,
                                 new_modification datetime,
                                 new_status text,
                                 last_archive_id integer,
                                 sweep_mark text,
                                 force_backup char(1),
                                 foreign key (last_archive_id) references s3_archive (archive_id)
                                 )
                              ''')
        self.connection.execute('''create unique index if not exists files_1 on files (
                                 client_fqdn,
                                 backup_root,
                                 relative_path
                                 )
                              ''')

    def ddl_create_table_file_archive_records(self):
        self.connection.execute('''create table if not exists file_archive_records (
                                 file_id integer not null,
                                 archive_id integer not null,
                                 file_size integer not null,
                                 file_modification datetime not null,
                                 status text not null,
                                 foreign key (archive_id) references s3_archives (archive_id)
                                 foreign key (file_id) references files (file_id)
                                 primary key (file_id, archive_id)
                                 )
                              ''')
        #   self.connection.execute('''create unique index if not exists file_archive_records_1 on file_archive_records_records (
        #                               file_host_fqdn,
        #                               file_backup_root,
        #                               file_path,
        #                              )
        #                           ''')

    def ddl_create_table_s3_archives(self):
        self.connection.execute('''create table if not exists s3_archives (
                                 archive_id integer primary key,
                                 cloud text not null,
                                 region text not null,
                                 bucket text not null,
                                 archive_file_name text not null,
                                 total_size integer not null,
                                 relevant_size integer not null,
                                 status text not null,
                                 sha256 text,
                                 created datetime default current_timestamp
                                 )
                              ''')
        self.connection.execute('''create unique index if not exists s3_archives_1 on s3_archives (
                                 cloud,
                                 region,
                                 bucket,
                                 archive_file_name
                                 )
                              ''')

    # WARN: need to change this if we want simultaneous backups
    def prepare_backup(self):
        # self.connection.execute('''update file_archive_records
        #                          set status = 'failed'
        #                          where status = 'pending_upload'
        #                       ''')
        # self.connection.execute('''update s3_archives
        #                          set status = 'failed'
        #                          where status = 'pending_upload'
        #                       ''')
        self.connection.execute('''delete from file_archive_records
                                 where status = 'pending_upload'
                              ''')
        self.connection.execute('''delete from s3_archives
                                 where status = 'pending_upload'
                              ''')
        self.connection.execute('''update files
                                 set new_size = null,
                                       new_modification = null,
                                       new_status = null
                                 where new_status is not null
                              ''')

    def add_backup_client_config(self, client_fqdn: str, backup_root: str, key_file_path: str,
                                 cloud: str, region: str, credentials: str, bucket: str):
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  insert into backup_client_configs(client_fqdn, backup_root, status, key_file_path,
                                                      cloud, region, credentials, bucket)
                  values(?,?,?,?,?,?,?,?)
                  '''
            cursor.execute(query, (client_fqdn, backup_root, "active", key_file_path,
                                   cloud, region, credentials, bucket))

    def get_active_client_configs(self):
        entries = []
        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  select cloud, region, credentials, bucket, client_fqdn, backup_root, key_file_path
                  from backup_client_configs
                  where status = 'active'
                  '''
            cursor.execute(query)

            for row in cursor:
                entries.append(ClientConfig(row["cloud"], row["region"], row["credentials"], row["bucket"],
                                            row["client_fqdn"], row["backup_root"], row["key_file_path"]))

        return entries

    def upsert_client_file(self, client_fqdn, backup_root, rel_path, metadata: os.stat_result, status):
        datetime_str = self.epoch2fmt(metadata.st_mtime)

        with self.connection:
            cursor = self.connection.cursor()
            query = '''
                  insert into files(client_fqdn, backup_root, relative_path, size, modification, status, sweep_mark, force_backup, new_size, new_modification, new_status)
                  values(?,?,?,?,?,?,'present','Y',?,?,'present')
                  on conflict(client_fqdn, backup_root, relative_path) do
                  update set
                     new_size = ?,
                     new_modification = ?,
                     new_status = 'present',
                     sweep_mark = 'present'
                  '''
            cursor.execute(query, (client_fqdn, backup_root, rel_path, metadata.st_size, datetime_str, status,
                                   metadata.st_size, datetime_str,
                                   metadata.st_size, datetime_str))

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

            # TODO move this to archive_uploaded() as the code is not shared
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

    def get_files_to_backup(self, client_fqdn, backup_root):
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

    def epoch2fmt(self, epoch) -> str:
        return time.strftime('%Y-%m-%d %H:%M:%S %Z', time.gmtime(epoch))

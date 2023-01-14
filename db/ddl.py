import sqlite3
import os

from dataclasses import dataclass


@dataclass()
class MaintainSchema():
    connection: sqlite3.Connection

    def __post_init__(self):
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

import sqlite3

from dataclasses import dataclass

from .schema_upgrade import SchemaUpgrade


@dataclass()
class SchemaUpgradeV0(SchemaUpgrade):
    connection: sqlite3.Connection
    schema_version: int = 0

    def __post_init__(self):
        self.upgrade()
        self.set_version()

    def upgrade(self):
        self.ddl_create_table_s3_archives()
        self.ddl_create_table_file_archive_records()
        self.ddl_create_table_files()
        self.ddl_create_table_backup_client_configs()

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

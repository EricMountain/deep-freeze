#!/usr/bin/env python3

import argparse
import os
import re
import sys
from datetime import datetime, timezone

from dataclasses import dataclass

from db import Database

@dataclass
class Restore:
    cloud_provider: str
    region: str
    backup_root: str
    target: str

    def __post_init__(self):
        self.db = Database()

    def run(self):
        self.stat_file()
        file_id = self.find_file_id()
        archives = self.find_archives(file_id)
        self.get_archive_details(archives)
        self.generate_restore_commands(archives)
        self.generate_restore_status_commands(archives)
        self.generate_s3_copy_commands(archives)
        self.generate_gpg_commands(archives)
        self.generate_untar_commands(archives)

    def stat_file(self):
        full_path = os.path.join(self.backup_root, self.target)
        print(f"\n-- Stat {full_path}:")
        try:
            stat = os.stat(full_path)
            print(f"{stat}")
            print(f"Mode: {stat.st_mode}")
            print(f"Permissions: {stat.st_mode & 0o777}")
            print(f"Owner ID: {stat.st_uid}")
            print(f"Group ID: {stat.st_gid}")
            print(f"File size: {stat.st_size} bytes")
            print(f"Last access time: {human_readable_epoch(stat.st_atime)}")
            print(f"Last modified time: {human_readable_epoch(stat.st_mtime)}")
            print(f"Last change time: {human_readable_epoch(stat.st_ctime)}")
        except FileNotFoundError as e:
            print(f"Target file does not exist: {e}")

    def find_file_id(self) -> int:
        pattern = self.utf8_to_query(self.target)
        file_ids = self.db.find_file(self.backup_root, pattern)
        print("\n-- File IDs")
        print(f"{file_ids}")
        if len(file_ids) > 1:
            print("Too many potential file IDs found, aborting")
            sys.exit(1)
        elif len(file_ids) == 0:
            print("Did not find the file in the backup archives, aborting")
            sys.exit(2)
        return file_ids[0]["file_id"]

    # Possibly only need this on MacOS.
    #
    # UTF8 supports encoding certain characters multiple different ways. For instance, "é" can be encoded:
    #
    # * \xc3\xa9 = UTF8 representation of the precomposed character U+00E9, the official Unicode character for "é"
    # * \x65\xcc\x81 = x65 is "e", xcc = combining diacritic mark acute accent (´) and x81 is a no-op.
    #
    # On MacOS it seems the long form has ended up being used in the deep-freeze DB, but when we type the character it’s the short
    # form. So we need to use wildcards in order to match (another solution would be to implement a collation function as SQLite
    # only supports byte level comparisons natively).
    def utf8_to_query(self, target: str) -> str:
        return re.sub('[^a-zA-Z0-9/ @_!^()-+*=%]', '%', target, flags=re.ASCII)

    def find_archives(self, file_id):
        archives = self.db.find_file_archives(file_id)
        print(f"\n-- Archives")
        for archive in archives:
            print(f"{archive}")
        return archives

    def get_archive_details(self, archives):
        for archive in archives:
            archive_id = archive["archive_id"]
            archive_details = self.db.get_archive_details(archive_id)[0]
            archive_file_name = archive_details["archive_file_name"]
            archive["archive_file_name"] = archive_file_name
            archive["bucket"] = archive_details["bucket"]
            archive["archive_dest_file_name"] = re.sub('/', '_', archive_file_name)
        return archives

    def generate_restore_commands(self, archives):
        print("\n-- Restore commands")
        for archive in archives:
            bucket = archive["bucket"]
            archive_file_name = archive["archive_file_name"]
            print(f"aws-vault exec <someone> -- aws s3api restore-object --bucket {bucket} --key \'{archive_file_name}.enc\' --restore-request \'{{\"Days\":5,\"GlacierJobParameters\":{{\"Tier\":\"Standard\"}}}}'")

    def generate_restore_status_commands(self, archives):
        print("\n-- Restore status commands")
        for archive in archives:
            bucket = archive["bucket"]
            archive_name = archive["archive_file_name"]
            print(f"aws-vault exec <someone> -- aws s3api head-object --bucket {bucket} --key \'{archive_name}.enc\'")

    def generate_s3_copy_commands(self, archives):
        print("\n-- S3 copy commands")
        for archive in archives:
            bucket = archive["bucket"]
            archive_file_name = archive["archive_file_name"]
            archive_dest_file_name = archive["archive_dest_file_name"]
            print(f"aws-vault exec <someone> -- aws s3 cp s3://{bucket}/{archive_file_name}.enc ./{archive_dest_file_name}")
        return archives

    def generate_gpg_commands(self, archives):
        print("\n-- GPG commands")
        for archive in archives:
            archive_dest_file_name = archive["archive_dest_file_name"]
            print(f"gpg -d {archive_dest_file_name}.enc > {archive_dest_file_name}")

    def generate_untar_commands(self, archives):
        print("\n-- Untar commands")
        target_components = self.target.split("/")
        target_file_name = target_components[-1]
        strip_count = len(target_components) - 1
        for archive in archives:
            archive_dest_file_name = archive["archive_dest_file_name"]
            dest_directory = re.sub("\.tar\.gz$", "", archive_dest_file_name)
            print(f"mkdir {dest_directory} && tar xzf -C {dest_directory} --strip-components={strip_count} {archive_dest_file_name} \"{self.target}\"")

def human_readable_epoch(t: float):
    return datetime.fromtimestamp(t, tz=timezone.utc)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepares file restores')

    parser.add_argument("--cloud-provider",
                        help="Cloud-provider of the backup",
                        type=str,
                        default="aws")
    parser.add_argument("--region",
                        help="Cloud-provider region of the backup",
                        type=str,
                        default="eu-north-1")
    parser.add_argument("--client-name",
                        help="Name of the client of the backup",
                        type=str,
                        required=True)
    parser.add_argument("--backup-root",
                        help="Root directory of the backup",
                        type=str,
                        required=True)
    parser.add_argument("--target",
                        help="Relative path of file to restore",
                        type=str,
                        required=True)
    args = parser.parse_args()

    print(f"{args}")

    restore = Restore(args.cloud_provider, args.region, args.backup_root, args.target)
    restore.run()

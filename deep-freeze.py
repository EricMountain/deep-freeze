#!/usr/bin/env python3

import os
import subprocess
import time
import tarfile

from dataclasses import dataclass

from db import Database, ClientConfig


@dataclass
class BackupProcessor():
    db: Database
    client_config: ClientConfig

    def __post_init__(self):
        self.key_file_path = self.client_config.key_file_path

        self.backup_frozen_time = time.time()
        self.backup_frozen_time_struct = time.gmtime(self.backup_frozen_time)

        # TODO use mktemp
        tmp_directory = time.strftime('/tmp/%Y/%m/%d', self.backup_frozen_time_struct)
        if not os.path.exists(tmp_directory):
            os.makedirs(tmp_directory)

        self.archive_sequence_nb = 0
        # TODO config
        self.archive_max_size_bytes = 200000000 # 200MB
        #self.s3_storage_class = "DEEP_ARCHIVE"
        self.s3_storage_class = "STANDARD"

    def run(self):
        self.db.prepare_backup()
        self.db.set_sweep_mark(self.client_config.client_fqdn, self.client_config.backup_root)
        self.scan()
        self.db.update_deleted_files_new_status(self.client_config.client_fqdn, self.client_config.backup_root)
        self.db.mark_files_for_backup(self.client_config.client_fqdn, self.client_config.backup_root)
        self.backup()

    def scan(self):
        for root, dirs, files in os.walk(self.client_config.backup_root, followlinks=False):
            for file in files:
                abs_path = os.path.join(root, file)
                # Trim root and trailing slash
                rel_path = abs_path[len(self.client_config.backup_root)+1:]
                metadata = os.lstat(abs_path)
                self.db.upsert_client_file(self.client_config.client_fqdn,
                                            self.client_config.backup_root,
                                            rel_path,
                                            metadata,
                                            "present")

    def backup(self):
        tar_size = 0
        tar_name = None
        tar_full_path = None
        tar = None
        tar_id = None
        for file in self.db.get_files_to_backup(self.client_config.client_fqdn, self.client_config.backup_root):
            if tar_name is None:
                tar_name = self.new_archive_name() + ".tar.gz"
                tar_full_path = "/tmp/" + tar_name
                tar = tarfile.open(name=tar_full_path, mode='x:gz')

                tar_id = self.db.new_archive(self.client_config.cloud, self.client_config.region,
                                                self.client_config.bucket, tar_name)

            # Add file to tar
            print(f"{file['relative_path']} {file['new_size']} -> {tar_name}")
            tar.add(os.path.join(self.client_config.backup_root, file["relative_path"]))
            tar_size += file["new_size"]

            # Add file to archive index
            self.db.add_file_to_archive(tar_id, file["file_id"], file['new_size'], file['new_modification'])

            if tar_size >= self.archive_max_size_bytes:
                self.flush_tarball_to_s3(tar, tar_full_path, tar_id, tar_size, tar_name)
                tar_name = None
                tar_full_path = None
                tar = None
                tar_size = 0

        if tar is not None:
            self.flush_tarball_to_s3(tar, tar_full_path, tar_id, tar_size, tar_name)

    def flush_tarball_to_s3(self, tar: tarfile, tar_full_path: str, tar_id: int, tar_size: int, tar_name: str):
        tar.close()
        
        enc_name = tar_name + '.enc'
        enc_full_path = tar_full_path + '.enc'
        # TODO it would be smarter to use asymmetric here, it would improve security since we'd encrypt using public keys
        subprocess.run(f"gpg -c --pinentry-mode=loopback --passphrase-file {self.key_file_path} -o {enc_full_path} {tar_full_path}".split())
        # TODO calc sha256 of the enc file
        cmd = f"aws --profile {self.client_config.credentials}"
        cmd += f" s3 cp --storage-class {self.s3_storage_class}"
        cmd += f" {enc_full_path} s3://{self.client_config.bucket}/{enc_name}"
        subprocess.run(cmd.split())
        self.db.archive_uploaded(tar_id, tar_size)
        os.remove(tar_full_path)
        os.remove(enc_full_path)

    def new_archive_name(self) -> str:
        # datetime, client, bkp root, seqnb
        # NB - this shards into a hierarchy based on the date to limit per-directory file count
        datetime_str = time.strftime('%Y/%m/%d/%H-%M-%S', self.backup_frozen_time_struct)
        safe_bkp_root = self.safe_filename(self.client_config.backup_root)
        self.archive_sequence_nb += 1
        name = f"{datetime_str}_{self.client_config.client_fqdn}_{safe_bkp_root}_{self.archive_sequence_nb}"
        return name

    def safe_filename(self, filename: str) -> str:
        safe = filename.replace("/", "-").replace(".", "-").replace(" ", "-")
        safe = safe.replace("_", "-")
        if safe.startswith("-"):
            safe = safe[1:]
        if safe.endswith("-"):
            safe = safe[:len(safe)-1]
        return safe


class Worker():
    def __init__(self):
        self.db = Database()

    def run(self):
        client_configs = self.db.get_active_client_configs()
        for cc in client_configs:
            print(f"{cc}")
            BackupProcessor(self.db, cc).run()


w = Worker()
w.run()

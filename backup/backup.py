import os
import subprocess
import time
import tarfile
import tempfile

from dataclasses import dataclass

from db import Database, ClientConfig, File


@dataclass
class Backup():
    db: Database
    client_config: ClientConfig
    s3_storage_class: str = "DEEP_ARCHIVE"

    def __post_init__(self):
        self._get_config_settings()

        self.backup_frozen_time = time.time()
        self.backup_frozen_time_struct = time.gmtime(self.backup_frozen_time)

        # TODO destroy on exit
        tmpdir = None
        if ClientConfig.TMP_DIR in self.client_config.options and self.client_config.options[ClientConfig.TMP_DIR]:
            tmpdir = self.client_config.options[ClientConfig.TMP_DIR]
        self.tmp_directory = tempfile.mkdtemp(prefix="deep-freeze-", dir=tmpdir)
        if not os.path.exists(self.tmp_directory):
            os.makedirs(self.tmp_directory)

        self.archive_sequence_nb = 0

    def _get_config_settings(self):
        self.cross_devices = self.client_config.options[
            ClientConfig.BACKUPS_CROSS_DEVICES] == ClientConfig.YES
        # TODO config
        self.archive_max_size_bytes = 500000000  # 500MB
        self.key_file_path = self.client_config.key_file_path

    def run(self):
        self.run_backup()

    def run_backup(self):
        self.prepare_backup()
        self.db.set_sweep_mark(
            self.client_config.client_fqdn, self.client_config.backup_root)
        self.scan()
        self.db.update_deleted_files_new_status(
            self.client_config.client_fqdn, self.client_config.backup_root)
        self.db.mark_files_for_backup(
            self.client_config.client_fqdn, self.client_config.backup_root)
        self.backup()

    # WARN: need to change this if we want simultaneous backups
    def prepare_backup(self):
        self.db.connection.execute('''delete from file_archive_records
                                   where status = 'pending_upload'
                              ''')
        self.db.connection.execute('''delete from s3_archives
                                   where status = 'pending_upload'
                              ''')
        self.db.connection.execute('''update files
                                   set new_size = null,
                                       new_modification = null,
                                       new_status = null
                                   where new_status is not null
                              ''')

    def scan(self):
        self.db.connection.execute("BEGIN")
        for root, dirs, files in os.walk(self.client_config.backup_root, followlinks=False):
            if not self.cross_devices:
                dirs[:] = [dir for dir in dirs if not os.path.ismount(
                    os.path.join(root, dir))]
            for file in files:
                File(self.db, self.client_config, root, file).upsert()
        self.db.connection.commit()

    def backup(self):
        tar_size = 0
        tar_name = None
        tar_full_path = None
        tar = None
        tar_id = None
        files_to_backup = self.db.get_files_to_backup(self.client_config.client_fqdn,
                                                      self.client_config.backup_root)
        files_to_backup_count = len(files_to_backup)
        for idx, file in enumerate(files_to_backup):
            if tar_name is None:
                tar_name = self.new_archive_name() + ".tar.gz"
                tar_full_path = os.path.join(self.tmp_directory, tar_name)
                tar_base = os.path.dirname(tar_full_path)
                print(f"tmpdir: {self.tmp_directory}, tar base: {tar_base}")
                if not os.path.exists(tar_base):
                    print(f"tar base: {tar_base} creating")
                    os.makedirs(tar_base)
                else:
                    print(f"tar base: {tar_base} exists")
                tar = tarfile.open(name=tar_full_path, mode='x:gz')

                print(f"New archive: {tar_name}")
                tar_id = self.db.new_archive(self.client_config.cloud, self.client_config.region,
                                             self.client_config.bucket, tar_name)

            # if (files_to_backup_count > 100 and idx % 10 == 1) or files_to_backup_count <= 100:
            #     print(f"{file['relative_path']} {file['new_size']} -> {tar_name}",
            #           end="\r", flush=True)
            print(f"{file['relative_path']} {file['new_size']} -> {tar_name}")

            try:
                tar.add(os.path.join(
                    self.client_config.backup_root, file["relative_path"]))
            except FileNotFoundError as e:
                # File has been deleted in the interim.
                print(f'File disappeared: {file["relative_path"]}, {e}')
            except tarfile.TarError as e:
                # File may be unreadable (permissions), or some other error
                # TODO Determine cases and handle appropriately
                print(f'Failed to add {file["relative_path"]}: {e}')

            # File successfully added to the tarball, so account for its size and add to archive index
            tar_size += file["new_size"]
            self.db.add_file_to_archive(tar_id, file["file_id"],
                                        file['new_size'], file['new_modification'])

            if tar_size >= self.archive_max_size_bytes:
                self.flush_tarball_to_s3(tar, tar_full_path, tar_id, tar_size,
                                         tar_name)
                tar_name = None
                tar_full_path = None
                tar = None
                tar_size = 0

        if tar is not None:
            self.flush_tarball_to_s3(tar, tar_full_path, tar_id, tar_size,
                                     tar_name)

        # Flush output
        # print()
        # print("Backup complete")

    def flush_tarball_to_s3(self, tar: tarfile, tar_full_path: str, tar_id: int, tar_size: int, tar_name: str):
        tar.close()
        enc_name = tar_name + '.enc'
        enc_full_path = tar_full_path + '.enc'
        # TODO it would be smarter to use asymmetric here; would improve security since we'd encrypt using public keys
        subprocess.run(
            f"gpg -c --pinentry-mode=loopback --passphrase-file {self.key_file_path} -o {enc_full_path} {tar_full_path}".split())
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
        # NB - this shards archives into a hierarchy based on the date to limit per-directory file count
        datetime_str = time.strftime('%Y/%m/%d/%H-%M-%S',
                                     self.backup_frozen_time_struct)
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
            safe = safe[:len(safe) - 1]
        return safe

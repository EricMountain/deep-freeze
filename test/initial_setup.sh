#!/usr/bin/env bash

set -euo pipefail
#set -x

# Ensure we die if the binary is missing (but we don't want to die right away
# if we're running on bare metal, we want a chance to error nicely)
type systemd-detect-virt >/dev/null
case $(systemd-detect-virt) in
docker) ;;
*)
    echo Fatal: tests need to be run inside a container
    exit 1
    ;;
esac

[[ ! -d ~/.deep-freeze-backups ]] && mkdir ~/.deep-freeze-backups
rm -f ~/.deep-freeze-backups/deep-freeze-backups.db

dd if=/dev/urandom of=/deep-freeze/test/key bs=1024 count=1

if [[ -z ${test_root} || ! -d ${test_root} ]]; then
    echo Need test_root set and directory created
    exit 1
fi

if [[ -z ${test_root2} || ! -d ${test_root2} ]]; then
    echo Need test_root2 set and directory created
    exit 1
fi

if [[ -z ${temp_work_dir} || ! -d ${temp_work_dir} ]]; then
    echo -- Need temp_work_dir set to test --temp-directory
    exit 1
fi

../create-config.py --cloud-provider=aws --region=eu-north-1 --aws-profile=toto --bucket=bucket \
    --client-name="test-host" --backup-root=${HOME}/.deep-freeze-backups \
    --key-file=/deep-freeze/test/key

../create-config.py --cloud-provider=aws --region=eu-north-1 --aws-profile=toto --bucket=bucket \
    --client-name="test-host" --backup-root="${test_root}" \
    --key-file=/deep-freeze/test/key --no-cross-devices

sqlite3 -echo -header ~/.deep-freeze-backups/deep-freeze-backups.db \
    "insert into backup_client_configs_exclusions(client_fqdn, backup_root, pattern) values ('test-host', '${test_root}', '/excluded_directory1/.*')"

sqlite3 -echo -header ~/.deep-freeze-backups/deep-freeze-backups.db \
    "insert into backup_client_configs_exclusions(client_fqdn, backup_root, pattern) values ('test-host', '${test_root}', '/a1/excluded_directory2/.*')"

sqlite3 -echo -header ~/.deep-freeze-backups/deep-freeze-backups.db \
    "insert into backup_client_configs_exclusions(client_fqdn, backup_root, pattern) values ('test-host', '${test_root}', '/excluded_file1\.dat')"

sqlite3 -echo -header ~/.deep-freeze-backups/deep-freeze-backups.db \
    "insert into backup_client_configs_exclusions(client_fqdn, backup_root, pattern) values ('test-host', '${test_root}', '.*/excluded_file2\..*')"

../create-config.py --cloud-provider=aws --region=eu-north-1 --aws-profile=toto --bucket=bucket \
    --client-name="test-host" --backup-root="${test_root2}" \
    --key-file=/deep-freeze/test/key --manual-only --temp-directory="${temp_work_dir}"

sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select * from deep_freeze_metadata;"

sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select * from backup_client_configs; select * from backup_client_configs_options; select * from backup_client_configs_exclusions;"

mkdir -p "${test_root}/a1/b1/c1"
mkdir -p "${test_root}/a1/b1/c2"
mkdir -p "${test_root}/d1/e1/f1"
mkdir -p "${test_root}/d1/e2/f2"

dd if=/dev/urandom of="${test_root}/a1/b1/c1/c1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/a1/b1/c1/c1_2.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e1/f1/f1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=2

dd if=/dev/urandom of="${test_root2}/some_file" bs=1k count=1

# Create files we want excluded from the backups

mkdir -p "${test_root}/excluded_directory1/b1/c1"
dd if=/dev/urandom of="${test_root}/excluded_directory1/b1/c1/c1_1.dat" bs=1k count=2

mkdir -p "${test_root}/a1/excluded_directory2/c1"
dd if=/dev/urandom of="${test_root}/a1/excluded_directory2/c1/c1_1.dat" bs=1k count=2

dd if=/dev/urandom of="${test_root}/excluded_file1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/a1/b1/c1/excluded_file2.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e2/f2/excluded_file2.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e2/f2/not_initially_excluded_file3.dat" bs=1k count=2

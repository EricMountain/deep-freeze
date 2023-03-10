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

../create-config.py --cloud-provider=aws --region=eu-north-1 --aws-profile=toto --bucket=bucket \
  --client-name="test-host" --backup-root=${HOME}/.deep-freeze-backups \
  --key-file=/deep-freeze/test/key

../create-config.py --cloud-provider=aws --region=eu-north-1 --aws-profile=toto --bucket=bucket \
  --client-name="test-host" --backup-root="${test_root}" \
  --key-file=/deep-freeze/test/key --no-cross-devices

sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
  "select * from deep_freeze_metadata;"

sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
  "select * from backup_client_configs; select * from backup_client_configs_options;"

mkdir -p "${test_root}/a1/b1/c1"
mkdir -p "${test_root}/a1/b1/c2"
mkdir -p "${test_root}/d1/e1/f1"
mkdir -p "${test_root}/d1/e2/f2"

# mkdir -p "${test_root}/other_dev"
# mount -o bind /mnt/other_dev_vol "${test_root}/other_dev"

dd if=/dev/urandom of="${test_root}/a1/b1/c1/c1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/a1/b1/c1/c1_2.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e1/f1/f1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=2

# cd "${test_root}"
# for i in $(seq 4) ; do
#  mkdir $i
#  cd $i
#  for j in $(seq 4) ; do
#    mkdir $j
#    cd $j
#    for k in $(seq 10) ; do
#      touch $k
#    done
#    cd ..
#  done
#  cd ..
# done
# cd /deep-freeze/test

time ../deep-freeze.py

# FIXME Ensure archive name changes thanks to timestamp
sleep 1

# Ensure the size is different so we detect a change
dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=3

time ../deep-freeze.py

rm "${test_root}/a1/b1/c1/c1_1.dat"

time ../deep-freeze.py

sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
  "select * from files; select * from file_archive_records; select * from s3_archives;"

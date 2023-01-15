#!/usr/bin/env bash

set -euo pipefail
set -x

[[ ! -d ~/.deep-freeze-backups ]] && mkdir ~/.deep-freeze-backups
rm -f ~/.deep-freeze-backups/deep-freeze-backups.db
dd if=/dev/urandom of=/deep-freeze/test/key bs=1024 count=1

test_root=$(mktemp -d)
../create-config.py --cloud-provider=aws --region=eu-north-1 --aws-profile=toto --bucket=bucket \
                    --client-name="test-host" --backup-root="${test_root}" --key-file=/deep-freeze/test/key

mkdir -p "${test_root}/a1/b1/c1"
mkdir -p "${test_root}/a1/b1/c2"
mkdir -p "${test_root}/d1/e1/f1"
mkdir -p "${test_root}/d1/e2/f2"

dd if=/dev/urandom of="${test_root}/a1/b1/c1/c1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/a1/b1/c1/c1_2.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e1/f1/f1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=2

../deep-freeze.py

# Ensure the size is different so we detect a change
dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=3

../deep-freeze.py

rm "${test_root}/a1/b1/c1/c1_1.dat"

../deep-freeze.py

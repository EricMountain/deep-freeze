#!/usr/bin/env bash

set -euo pipefail
set -x

[[ ! -d ~/.deep-freeze-backups ]] && mkdir ~/.deep-freeze-backups
rm -f ~/.deep-freeze-backups/deep-freeze-backups.db
./create_test_config.py

#testroot=$(mktemp -d)
testroot=/deep-freeze/test/root
echo testkey > /deep-freeze/test/key

mkdir -p "${testroot}/a1/b1/c1"
mkdir -p "${testroot}/a1/b1/c2"
mkdir -p "${testroot}/d1/e1/f1"
mkdir -p "${testroot}/d1/e2/f2"

dd if=/dev/urandom of="${testroot}/a1/b1/c1/c1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${testroot}/a1/b1/c1/c1_2.dat" bs=1k count=2
dd if=/dev/urandom of="${testroot}/d1/e1/f1/f1_1.dat" bs=1k count=2
dd if=/dev/urandom of="${testroot}/d1/e2/f2/f2_1.dat" bs=1k count=2

../deep-freeze.py

# We need to ensure the file modification time won't be in the same second
sleep 1
dd if=/dev/urandom of="${testroot}/d1/e2/f2/f2_1.dat" bs=1k count=2

../deep-freeze.py

rm "${testroot}/a1/b1/c1/c1_1.dat"

../deep-freeze.py

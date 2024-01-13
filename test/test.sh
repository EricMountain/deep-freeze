#!/usr/bin/env bash

set -euo pipefail
set -x

# https://stackoverflow.com/a/246128
this_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

cd ${this_script_dir}
docker build -t deep-freeze-test:0.1 .. -f Dockerfile

test_root=$(mktemp -d -u)
other_dev_vol=$(mktemp -d)

touch ${other_dev_vol}/do_not_backup_this_file

docker run --rm -t -v ${other_dev_vol}:${test_root}/other_dev_vol -e test_root=${test_root} deep-freeze-test:0.1

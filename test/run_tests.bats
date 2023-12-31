#!/usr/bin/env -S bats -x --pretty --verbose-run
# For debugging: --show-output-of-passing-tests

setup_file() {
  export test_root2=$(mktemp -d)
  export temp_work_dir=$(mktemp -d)
  ./initial_setup.sh
}

setup() {
  bats_load_library 'bats-support'
  bats_load_library 'bats-assert'
}

# Test automatic backups

@test "Run backup 1" {
  run ../deep-freeze.py
  assert_success
}

@test "Check test_root files have been loaded" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files where backup_root = '${test_root}'"
  assert_output "4"
}

@test "Check deep-freeze files have been loaded too" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files"
  assert_output "5"
}

@test "Check test_root has been backed up" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files f inner join file_archive_records far using (file_id) where f.backup_root = '${test_root}' and far.status='uploaded'"
  assert_output "4"
}

@test "Check test_root2 has not been loaded as it is manually backed up" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files where backup_root = '${test_root2}'"
  assert_output "0"
}

@test "Ensure archive name will change for next backup" {
  run sleep 1
  assert_success
}

# Verify backups are incremental

@test "Make a change in test_root" {
  # Ensure the size is different so we detect a change
  dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=3
}

@test "Run backup 2" {
  run ../deep-freeze.py
  assert_success
}

@test "Check superseded and uploaded file counts including deep-freeze database" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from file_archive_records where status='uploaded'"
  assert_output "5"

  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from file_archive_records where status='superseded'"
  assert_output "2"
}

@test "Delete a file" {
  run rm "${test_root}/a1/b1/c1/c1_1.dat"
  assert_success
}

@test "Run backup 3" {
  run ../deep-freeze.py
  assert_success
}

@test "Check deleted file detected" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files where relative_path = 'a1/b1/c1/c1_1.dat' and status = 'absent'"
  assert_output "1"

  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from file_archive_records where status='deleted'"
  assert_output "1"
}

# Test manual backups

@test "Make a change in test_root that will not be backed up" {
  # Ensure the size is different so we detect a change
  dd if=/dev/urandom of="${test_root}/d1/e2/f2/f2_1.dat" bs=1k count=4
}

@test "Run test_root2 backup" {
  run ../deep-freeze-manual.py --cloud-provider=aws --region=eu-north-1 --client-name="test-host" --backup-root="${test_root2}"
  assert_success
}

@test "Check test_root2 has been loaded" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files where backup_root = '${test_root2}'"
  assert_output "1"
}

@test "Check test_root2 has been backed up" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from file_archive_records where status='uploaded'"
  assert_output "5"
}

@test "Check the change in test_root was not backed up" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files where relative_path = 'd1/e2/f2/f2_1.dat' and size = 3072"
  assert_output "1"
}

@test "Check manual backup used configured temp directory" {
  run bash -c "find ${temp_work_dir} | wc -l"
  assert_output "5"
}

# Test file restore command generator

@test "Prepare file restore" {
  cd "${test_root}"
  run /deep-freeze/deep-freeze-restore.py --client-name="test-host" --backup-root="${test_root}" --target=d1/e2/f2/f2_1.dat
  assert_success
}

# Test purge of superseded archives

@test "Ensure all test_root files are updated relative to first backup" {
  for f in $(find ${test_root} -type f) ; do
    dd if=/dev/urandom of="${f}" bs=1k count=3
  done
}

@test "Run backup 4" {
  run ../deep-freeze.py
  assert_success
}

@test "Increase age of first two archives" {
  run sqlite3 -echo ~/.deep-freeze-backups/deep-freeze-backups.db \
    "update s3_archives set created = '$(date -d "7 months ago" "+%Y-%m-%d %H:%M:%S")' where archive_id in (1, 2)"
  assert_success
}

@test "Run backup 5" {
  run ../deep-freeze.py
  assert_success
}

@test "Check old superseded archives have been deleted" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from s3_archives where status='deleted'"
  assert_output "2"
}

# Debugging

# @test "Force error to get DB contents" {
#   sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
#       "select * from files; select * from file_archive_records; select * from s3_archives; select * from backup_client_configs; select * from backup_client_configs_options"
#   find ${temp_work_dir}
#   exit 1
# }


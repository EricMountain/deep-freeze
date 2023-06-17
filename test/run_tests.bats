#!/usr/bin/env -S bats -x --pretty --verbose-run

setup_file() {
  export test_root2=$(mktemp -d)
  ./initial_setup.sh
}

setup() {
  bats_load_library 'bats-support'
  bats_load_library 'bats-assert'
}

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

@test "Check test_root2 has not been loaded" {
  run sqlite3 -echo -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
    "select count(*) from files where backup_root = '${test_root2}'"
  assert_output "0"
}

@test "Ensure archive name will change for next backup" {
  run sleep 1
  assert_success
}

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

# @test "Force error to get DB contents" {
#   sqlite3 -echo -header -readonly ~/.deep-freeze-backups/deep-freeze-backups.db \
#       "select * from files; select * from file_archive_records; select * from s3_archives; select * from backup_client_configs; select * from backup_client_configs_options"
#   exit 1
# }


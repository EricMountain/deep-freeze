# Deep Freeze - Yet Another Backup System

`deep-freeze` backs up files to Amazon S3\. By default, it uses the Glacier Deep Archive tier for the cheapest possible storage: the assumption is that we will only rarely restore, for instance in the case of total loss of a disk.

Since `deep-freeze` cannot read files in Deep Archive quickly and cheaply, backup state is held in an SQLite3 database that should also be backed up.

## Installation

- Clone the repository.
- Install Python 3.
- Configure access to an Amazon S3 bucket and set up an appropriate IAM user with AWS CLI access.

## Configuration

```shell
mkdir ${HOME}/.deep-freeze-backups
<<Create a password/key file, e.g. ${HOME}/.deep-freeze-backups/symmetric_key>>
./create-config.py --cloud-provider=aws \
                   --region=<region name> \
                   --aws-profile=<AWS CLI user profile> \
                   --bucket=<target bucket name> \
                   --client-name=<host name> \
                   --backup-root=<path to back up> \
                   --key-file=${HOME}/.deep-freeze-backups/symmetric_key
```

Ensure the key file is backed up somewhere safe, e.g. a password manager.

(A future version will support the use of public key encryption for improved security.)

## Run

```shell
./deep-freeze.py
```

Processes all configured backups in turn.

## Scheduled runs

To set up a launchd job that will attempt to run backups hourly if:

* on AC power,
* Internet access is available,
* and the last successful backup is at least 24h old

Edit `install/[CHOOSE_A_REVERSE_FQDN_PREFIX].deep-freeze.plist`, fill out placeholders and save in ~/.deep-freeze-backups, then:

```shell
cd ~/Library/LaunchAgents
ln -s ~/.deep-freeze-backups/[CHOOSE_A_REVERSE_FQDN_PREFIX].deep-freeze.plist
launchctl load ~/Library/LaunchAgents/[CHOOSE_A_REVERSE_FQDN_PREFIX].deep-freeze.plist
```

To start the job manually:

```shell
launchctl start [CHOOSE_A_REVERSE_FQDN_PREFIX].deep-freeze
```

## Restoring files from backup

Identify archives for a file to restore and generate the commands to restore the relevant S3 objects from Glacier (`restore-object`), monitor progress (`head-object`) of the restore and copy the file (`cp`):

```shell
deep-freeze-restore.py --client-name $(hostname) --backup-root $(pwd) --target "relative_path_to_file_to_restore"
```

* Trigger the restore from Glacier.
* Check for completion, it will take a few hours.
* Copy the restored object locally.
* Decrypt the archive: `gpg -d x.tar.gz.enc > x.tar.gz`.
* Untar the archive, extracting the desired file: `tar xzf x.tar.gz --strip-components=<Y> -C <destination> "relative_path_to_file"`

## Exclusions (experimental)

Files/directories can be excluded from backups: exclusions are defined using regexp patterns.

Exclusions are currently added through DML statements issued against the database directly, there is no helper CLI yet. For example:

```shell
sqlite3 -echo -header ~/.deep-freeze-backups/deep-freeze-backups.db \
    "insert into backup_client_configs_exclusions(client_fqdn, backup_root, pattern) values ('test-host', '${test_root}', '/a1/excluded_directory2/.*')"
```

### Evolution

It’s likely exclusions will evolve in a non-backward-compatible way once Python 3.13 is available, bringing support for [recursive wildcards in pathlib.PurePath.match()](https://github.com/python/cpython/issues/73435). This syntax would simplify UX.

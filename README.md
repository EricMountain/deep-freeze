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

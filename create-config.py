#!/usr/bin/env python3

import argparse

from db import Database, ClientConfig


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Creates a backup configuration')

    parser.add_argument("--cloud-provider",
                        help="Cloud-provider used for archive storage",
                        type=str,
                        default="aws")
    parser.add_argument("--region",
                        help="Cloud-provider region backups containing the archive bucket",
                        type=str,
                        default="eu-north-1")
    parser.add_argument("--aws-profile",
                        help="AWS profile to use for upload",
                        type=str,
                        required=True)
    parser.add_argument("--bucket",
                        help="Cloud-provider S3/blob bucket where archives are stored",
                        type=str,
                        required=True)
    parser.add_argument("--client-name",
                        help="Name of the client",
                        type=str,
                        required=True)
    parser.add_argument("--backup-root",
                        help="Directory to backup, a local directory path",
                        type=str,
                        required=True)
    parser.add_argument("--key-file",
                        help="Path to the symmetric key to use for encrypting archives",
                        type=str,
                        required=True)
    parser.add_argument("--cross-devices",
                        help="Whether backups of this directory will cross mount points",
                        action=argparse.BooleanOptionalAction,
                        default=True)
    parser.add_argument("--manual-only",
                        help="Whether backups of this directory should only be done manually",
                        action=argparse.BooleanOptionalAction,
                        default=False)

    args = parser.parse_args()

    options = {}
    options[ClientConfig.BACKUPS_CROSS_DEVICES] = ClientConfig.YES if args.cross_devices else ClientConfig.NO
    options[ClientConfig.MANUAL_ONLY] = ClientConfig.YES if args.manual_only else ClientConfig.NO

    db = Database()
    config = ClientConfig(args.cloud_provider, args.region, args.aws_profile, args.bucket, args.client_name,
                          args.backup_root, args.key_file, options, db)
    config.add_to_database()

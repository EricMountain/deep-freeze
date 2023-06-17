#!/usr/bin/env python3

import argparse

from backup import Coordinator

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Runs backups')

    parser.add_argument("--cloud-provider",
                        help="Cloud-provider of the manual backup to trigger",
                        type=str,
                        default="aws")
    parser.add_argument("--region",
                        help="Cloud-provider region of the manual backup to trigger",
                        type=str,
                        default="eu-north-1")
    parser.add_argument("--client-name",
                        help="Name of the client of the manual backup to trigger",
                        type=str,
                        required=True)
    parser.add_argument("--backup-root",
                        help="Root directory of the manual backup to trigger",
                        type=str,
                        required=True)
    args = parser.parse_args()

    print(f"{args}")
    c = Coordinator()
    c.run_manual(args.cloud_provider, args.region, args.client_name, args.backup_root)

from dataclasses import dataclass


@dataclass
class ClientConfig():
    cloud: str
    region: str
    credentials: str
    bucket: str
    client_fqdn: str
    backup_root: str
    key_file_path: str

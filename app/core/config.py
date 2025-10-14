"""Application configuration helpers."""

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LinkChatConfig:
    iface: str
    ethertype: int
    name: str
    beacon_interval: float
    peers_file: str
    reset_peers_on_start: bool
    inbox_dir: str
    chunk_size: int
    msg_retry_interval: float
    msg_max_retries: int
    file_retry_interval: float
    file_max_retries: int


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip() == "1"


def load_config(env: Mapping[str, str] | None = None) -> LinkChatConfig:
    """Build a configuration object from environment variables."""

    env_mapping = os.environ if env is None else env

    msg_retry_interval = float(env_mapping.get("MSG_RETRY_INTERVAL", "3.0"))
    file_retry_fallback = str(msg_retry_interval)

    return LinkChatConfig(
        iface=env_mapping.get("IFACE", "eth0"),
        ethertype=int(env_mapping.get("ETHERTYPE", "0x88B5"), 0),
        name=env_mapping.get("NAME", "node"),
        beacon_interval=float(env_mapping.get("BEACON_INTERVAL", "5.0")),
        peers_file=env_mapping.get("PEERS_FILE", "/data/peers.json"),
        reset_peers_on_start=_env_bool(env_mapping.get("RESET_PEERS_ON_START"), True),
        inbox_dir=env_mapping.get("INBOX_DIR", "/data/inbox"),
        chunk_size=int(env_mapping.get("CHUNK_SIZE", "1300")),
        msg_retry_interval=msg_retry_interval,
        msg_max_retries=int(env_mapping.get("MSG_MAX_RETRIES", "3")),
        file_retry_interval=float(env_mapping.get("FILE_RETRY_INTERVAL", file_retry_fallback)),
        file_max_retries=int(env_mapping.get("FILE_MAX_RETRIES", "3")),
    )

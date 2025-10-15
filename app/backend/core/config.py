"""
config.py
~~~~~~~~~

Application configuration management from environment variables.

This module provides centralized configuration loading for LinkChat, translating
environment variables into a strongly-typed configuration object. All settings
have sensible defaults for quick startup.

Environment Variables:
    IFACE: Network interface name (default: "eth0")
    ETHERTYPE: Custom EtherType in hex (default: "0x88B5")
    NAME: Local peer identifier (default: "node")
    BEACON_INTERVAL: Seconds between discovery beacons (default: "5.0")
    PEERS_FILE: JSON file for peer persistence (default: "/data/peers.json")
    RESET_PEERS_ON_START: Clear peers on startup "1"=yes (default: yes)
    INBOX_DIR: Directory for received files (default: "/data/inbox")
    CHUNK_SIZE: File transfer chunk size in bytes (default: "1300")
    MSG_RETRY_INTERVAL: Seconds between message retries (default: "3.0")
    MSG_MAX_RETRIES: Maximum message retry attempts (default: "3")
    FILE_RETRY_INTERVAL: Seconds between chunk retries (default: MSG_RETRY_INTERVAL)
    FILE_MAX_RETRIES: Maximum chunk retry attempts (default: "3")

Example:
    >>> config = load_config()
    >>> config.iface
    'eth0'
    >>> config.chunk_size
    1300
"""

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LinkChatConfig:
    """
    Immutable configuration container for LinkChat application.

    This dataclass holds all runtime configuration parameters with type safety.
    Instances are frozen (immutable) to prevent accidental modification after
    initialization.

    Attributes:
        iface: Network interface name for raw socket binding (e.g., "eth0", "wlan0").

        ethertype: Custom EtherType identifier for frame filtering (0x0800-0xFFFF).
                   Default 0x88B5 is in the experimental range.

        name: Human-readable identifier for this host, broadcast in beacons.
              Should be unique on the local network segment.

        beacon_interval: Seconds between peer discovery beacon broadcasts.
                        Lower values = faster discovery but more network traffic.

        peers_file: Absolute path to JSON file for persisting discovered peers
                    across application restarts.

        reset_peers_on_start: If True, clears peer database on startup.
                             Useful for testing or when peer state is stale.

        inbox_dir: Directory where received files are stored.
                   Created automatically if doesn't exist.

        chunk_size: Maximum bytes per file transfer chunk.
                    Should be less than MTU (typically 1500) minus overhead.
                    Default 1300 leaves room for headers.

        msg_retry_interval: Seconds to wait before retransmitting unacknowledged
                           chat messages.

        msg_max_retries: Maximum chat message retransmission attempts before
                        considering delivery failed.

        file_retry_interval: Seconds to wait before retransmitting unacknowledged
                            file chunks.

        file_max_retries: Maximum file chunk retransmission attempts before
                         aborting transfer.

    Example:
        >>> config = LinkChatConfig(
        ...     iface="eth0",
        ...     ethertype=0x88B5,
        ...     name="MyHost",
        ...     beacon_interval=5.0,
        ...     peers_file="/data/peers.json",
        ...     reset_peers_on_start=True,
        ...     inbox_dir="/data/inbox",
        ...     chunk_size=1300,
        ...     msg_retry_interval=3.0,
        ...     msg_max_retries=3,
        ...     file_retry_interval=3.0,
        ...     file_max_retries=3
        ... )
    """

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
    max_peer_age_secs: float


def _parse_bool_env(value: str | None, default: bool) -> bool:
    """
    Parse boolean from environment variable string.

    Interprets "1" as True, anything else (or None) as False,
    with configurable default for missing values.

    Args:
        value: Environment variable value or None if not set.
        default: Value to return if environment variable is not set.

    Returns:
        bool: Parsed boolean value.

    Example:
        >>> _parse_bool_env("1", False)
        True
        >>> _parse_bool_env("0", False)
        False
        >>> _parse_bool_env(None, True)
        True
    """
    if value is None:
        return default
    return value.strip() == "1"


def load_config(env: Mapping[str, str] | None = None) -> LinkChatConfig:
    """
    Load configuration from environment variables with defaults.

    Reads configuration from the provided environment mapping (or os.environ
    if None). All values have sensible defaults for quick startup. Type
    conversion is performed automatically with appropriate error messages
    on invalid values.

    Args:
        env: Optional environment variable mapping. If None, uses os.environ.
             Useful for testing with custom configurations.

    Returns:
        LinkChatConfig: Populated configuration object ready for use.

    Raises:
        ValueError: If numeric values cannot be parsed (e.g., invalid float/int).

    Example:
        >>> config = load_config()
        >>> config.name
        'node'

        >>> # Custom environment for testing
        >>> test_env = {"NAME": "TestHost", "CHUNK_SIZE": "2000"}
        >>> config = load_config(env=test_env)
        >>> config.name
        'TestHost'
        >>> config.chunk_size
        2000

    Note:
        FILE_RETRY_INTERVAL defaults to MSG_RETRY_INTERVAL if not explicitly set,
        maintaining consistency between message and file retry timing.
    """
    env_mapping = os.environ if env is None else env

    # Parse message retry interval first (used as fallback for file retry)
    msg_retry_interval = float(env_mapping.get("MSG_RETRY_INTERVAL", "3.0"))
    file_retry_fallback = str(msg_retry_interval)

    return LinkChatConfig(
        iface=env_mapping.get("IFACE", "eth0"),
        ethertype=int(env_mapping.get("ETHERTYPE", "0x88B5"), 0),  # Base 0 = auto-detect hex
        name=env_mapping.get("NAME", "node"),
        beacon_interval=float(env_mapping.get("BEACON_INTERVAL", "5.0")),
        peers_file=env_mapping.get("PEERS_FILE", "/data/peers.json"),
        reset_peers_on_start=_parse_bool_env(env_mapping.get("RESET_PEERS_ON_START"), default=True),
        inbox_dir=env_mapping.get("INBOX_DIR", "/data/inbox"),
        chunk_size=int(env_mapping.get("CHUNK_SIZE", "1300")),
        msg_retry_interval=msg_retry_interval,
        msg_max_retries=int(env_mapping.get("MSG_MAX_RETRIES", "3")),
        file_retry_interval=float(env_mapping.get("FILE_RETRY_INTERVAL", file_retry_fallback)),
        file_max_retries=int(env_mapping.get("FILE_MAX_RETRIES", "3")),
        max_peer_age_secs=float(env_mapping.get("STALE_TIME_UNTIL_PRUNE", "90"))
    )

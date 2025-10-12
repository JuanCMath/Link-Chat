"""Adaptive protocol parameters for different network medium types.

Provides automatic parameter selection for message and file transfer protocols
based on the underlying physical medium (Ethernet vs Wi-Fi). The module detects
the network interface hardware type and returns optimized timeout, retry, and
chunk size values to match the reliability characteristics of the medium.

Ethernet interfaces (wired) have very low packet loss rates (< 0.1%) and low
latency, allowing aggressive parameters. Wi-Fi interfaces (wireless) experience
higher packet loss (5-15%) and variable latency, requiring more conservative
settings to ensure reliable delivery.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Linux kernel hardware type codes (from <linux/if_arp.h>)
# Ethernet and Ethernet-like interfaces
_ETHERNET_TYPES = {
    1,   # ARPHRD_ETHER - Ethernet 10/100/1000 Mbps
    6,   # ARPHRD_IEEE802 - Token Ring
    7,   # ARPHRD_ARCNET - ARCnet
    11,  # ARPHRD_PRONET - PROnet token ring
}

# Wi-Fi and wireless interfaces
_WIFI_TYPES = {
    801,  # ARPHRD_IEEE80211 - IEEE 802.11 (Wi-Fi)
    802,  # ARPHRD_IEEE80211_PRISM - Wi-Fi with Prism headers
    803,  # ARPHRD_IEEE80211_RADIOTAP - Wi-Fi with RadioTap headers
    804,  # ARPHRD_IEEE80211_RADIOTAP_COMPAT - Legacy RadioTap
    805,  # ARPHRD_IEEE80211_MONITOR - Wi-Fi monitor mode
    806,  # ARPHRD_PHONET - Nokia Phonet (wireless)
    808,  # ARPHRD_PHONET_PIPE - Phonet pipe endpoint
    809,  # ARPHRD_CAIF - CAIF (wireless)
}


class MediumFamily(Enum):
    """Classification of network medium types.
    
    Categorizes network interfaces into families with similar reliability
    and performance characteristics for protocol parameter selection.
    
    Attributes:
        ETHERNET: Wired Ethernet interfaces (high reliability, low latency).
        WIFI: Wireless Wi-Fi interfaces (moderate reliability, variable latency).
        UNKNOWN: Unrecognized or unsupported interface types (conservative defaults).
    """
    ETHERNET = "ethernet"
    WIFI = "wifi"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MessageParams:
    """Protocol parameters for text message transmission.
    
    Defines optimal settings for the MessageProtocol based on medium type.
    Text messages are typically small (< 10 KB) and use stop-and-wait ARQ
    with complete message acknowledgment.
    
    Attributes:
        max_payload: Maximum payload bytes per message before fragmentation.
            Smaller values reduce retransmission overhead on lossy mediums.
        ack_timeout: Seconds to wait for acknowledgment before retry.
            Higher values account for wireless latency and queueing delays.
        max_retries: Maximum transmission attempts before giving up.
            More retries compensate for higher Wi-Fi packet loss rates.
        inter_part_delay: Delay in seconds between sending message parts.
            Prevents buffer overflow on slower wireless interfaces.
    """
    max_payload: int
    ack_timeout: float
    max_retries: int
    inter_part_delay: float


@dataclass(frozen=True)
class FileParams:
    """Protocol parameters for file transfer operations.
    
    Defines optimal settings for the FileTransfer protocol based on medium type.
    File transfers can be large (MB to GB) and use per-chunk acknowledgment
    with selective retransmission for efficiency.
    
    Attributes:
        chunk_size: Size of each file chunk in bytes.
            Smaller chunks reduce wasted bandwidth when retransmitting on
            lossy Wi-Fi connections, at the cost of more ACK overhead.
        ack_timeout: Seconds to wait for chunk acknowledgment before retry.
            Longer timeouts accommodate wireless medium access delays.
        max_retries: Maximum retransmission attempts per chunk.
            Higher values ensure delivery despite Wi-Fi packet loss.
        inter_chunk_delay: Delay in seconds between sending chunks.
            Prevents congestion and allows receiver buffering on wireless.
    """
    chunk_size: int
    ack_timeout: float
    max_retries: int
    inter_chunk_delay: float


def detect_family(hardware_type: Optional[int]) -> MediumFamily:
    """Classify network interface by hardware type code.
    
    Maps Linux kernel hardware address type (ARPHRD_* constants) to a
    medium family category for parameter selection. Uses sysfs-provided
    hatype values read from /sys/class/net/{iface}/type.
    
    Args:
        hardware_type: Linux kernel hardware type code (e.g., 1 for Ethernet,
            801 for Wi-Fi), or None if unknown.
    
    Returns:
        MediumFamily.ETHERNET for wired interfaces, MediumFamily.WIFI for
        wireless interfaces, or MediumFamily.UNKNOWN for unrecognized types.
    """
    if hardware_type in _ETHERNET_TYPES:
        return MediumFamily.ETHERNET
    if hardware_type in _WIFI_TYPES:
        return MediumFamily.WIFI
    return MediumFamily.UNKNOWN


def message_params_for_family(family: MediumFamily) -> MessageParams:
    """Get optimal message protocol parameters for a medium family.
    
    Returns tuned settings for the MessageProtocol based on the reliability
    characteristics of the network medium. Ethernet uses aggressive parameters
    (short timeouts, few retries) due to its high reliability. Wi-Fi uses
    conservative parameters (long timeouts, more retries) to handle packet loss.
    
    Parameter Rationale:
    - Ethernet (0.01-0.1% loss): Fast ACKs (0.5s), minimal retries (3x), large
      payloads (1024 bytes) maximize throughput on reliable links.
    - Wi-Fi (5-15% loss): Longer ACKs (2.0s) account for medium access delays,
      more retries (5x) handle packet loss, smaller payloads (800 bytes) reduce
      retransmission overhead.
    - Unknown: Conservative middle-ground settings for safety.
    
    Args:
        family: Medium classification (ETHERNET, WIFI, or UNKNOWN).
    
    Returns:
        MessageParams instance with timeout, retry, and fragmentation settings
        optimized for the specified medium family.
    """
    if family is MediumFamily.ETHERNET:
        return MessageParams(
            max_payload=1024,
            ack_timeout=0.5,
            max_retries=3,
            inter_part_delay=0.005,
        )
    if family is MediumFamily.WIFI:
        return MessageParams(
            max_payload=800,
            ack_timeout=2.0,
            max_retries=5,
            inter_part_delay=0.01,
        )
    return MessageParams(
        max_payload=896,
        ack_timeout=1.5,
        max_retries=5,
        inter_part_delay=0.01,
    )


def file_params_for_family(family: MediumFamily) -> FileParams:
    """Get optimal file transfer parameters for a medium family.
    
    Returns tuned settings for the FileTransfer protocol based on the medium's
    reliability and throughput characteristics. File transfers use per-chunk
    acknowledgment, so chunk size directly affects retransmission efficiency.
    
    Parameter Rationale:
    - Ethernet (0.01-0.1% loss): Large chunks (1400 bytes) near MTU maximize
      throughput, short ACK timeout (0.8s), moderate retries (4x). Packet loss
      is rare, so aggressive settings work well.
    - Wi-Fi (5-15% loss): Smaller chunks (1200 bytes) reduce wasted bandwidth
      when retransmitting lost chunks. Longer timeout (2.0s) handles contention
      and medium access delays. More retries (7x) ensure delivery despite loss.
    - Unknown: Balanced settings for unrecognized mediums.
    
    Args:
        family: Medium classification (ETHERNET, WIFI, or UNKNOWN).
    
    Returns:
        FileParams instance with chunk size, timeout, and retry settings
        optimized for the specified medium family.
    """
    if family is MediumFamily.ETHERNET:
        return FileParams(
            chunk_size=1400,
            ack_timeout=0.8,
            max_retries=4,
            inter_chunk_delay=0.005,
        )
    if family is MediumFamily.WIFI:
        return FileParams(
            chunk_size=1200,
            ack_timeout=2.0,
            max_retries=7,
            inter_chunk_delay=0.01,
        )
    return FileParams(
        chunk_size=1300,
        ack_timeout=1.5,
        max_retries=6,
        inter_chunk_delay=0.008,
    )


def message_params_from_medium(medium: object) -> MessageParams:
    """Derive message protocol parameters from a network medium instance.
    
    Convenience function that extracts the hardware type from a medium object
    (typically AFPacketMedium or AFPacketMediumEthWifi), classifies it into
    a medium family, and returns the corresponding optimized message parameters.
    
    The function uses duck typing to access the 'hatype' attribute, making it
    compatible with any medium class that exposes hardware type information.
    If hatype is not available, defaults to UNKNOWN family parameters.
    
    Args:
        medium: Network medium object with optional 'hatype' attribute
            (e.g., AFPacketMediumEthWifi instance).
    
    Returns:
        MessageParams optimized for the detected medium type.
    
    Example:
        >>> medium = AFPacketMediumEthWifi("eth0", 0x88B5)
        >>> params = message_params_from_medium(medium)
        >>> params.ack_timeout
        0.5  # Fast timeout for Ethernet
    """
    hatype = getattr(medium, "hatype", None)
    family = detect_family(hatype)
    return message_params_for_family(family)


def file_params_from_medium(medium: object) -> FileParams:
    """Derive file transfer parameters from a network medium instance.
    
    Convenience function that extracts the hardware type from a medium object
    (typically AFPacketMedium or AFPacketMediumEthWifi), classifies it into
    a medium family, and returns the corresponding optimized file transfer
    parameters.
    
    The function uses duck typing to access the 'hatype' attribute, making it
    compatible with any medium class that exposes hardware type information.
    If hatype is not available, defaults to UNKNOWN family parameters.
    
    Args:
        medium: Network medium object with optional 'hatype' attribute
            (e.g., AFPacketMediumEthWifi instance).
    
    Returns:
        FileParams optimized for the detected medium type.
    
    Example:
        >>> medium = AFPacketMediumEthWifi("wlan0", 0x88B5)
        >>> params = file_params_from_medium(medium)
        >>> params.chunk_size
        1200  # Smaller chunks for Wi-Fi reliability
    """
    hatype = getattr(medium, "hatype", None)
    family = detect_family(hatype)
    return file_params_for_family(family)


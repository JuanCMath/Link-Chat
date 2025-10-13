"""Link layer networking module for direct layer-2 communication.

This module provides all the core networking functionality for LinkChat,
including CSMA collision avoidance, framing, reliable transfers, file
chunking, and raw socket interfaces.

Main Components:
    - AFPacketMedium: Basic AF_PACKET socket interface
    - CSMAPersistent: CSMA/CA medium access control
    - LinkLayer: Frame assembly/disassembly and routing
    - FileTransfer: File and folder transfer with chunking
    - ReliableTransfer: ACK-based reliability layer

Example:
    >>> from linkchat.link import AFPacketMedium, LinkLayer
    >>> medium = AFPacketMedium(interface="eth0")
    >>> layer = LinkLayer(medium)
    >>> layer.start()
"""

from .medium.af_packet_medium import AFPacketMedium
from .medium.af_packet_medium_eth_wifi import AFPacketMediumEthWifi
from .mac.csma_persistent import CSMAPersistent
from .core.link_layer import LinkLayer, FrameType, LinkFrame
from .transfer.file_transfer import FileTransfer, FileTransferState
from .transfer.transfer_reliability import ReliableTransfer
from .peer_discovery import PeerInfo, PeerDiscoveryService
from .core.message_protocol import MessageProtocol

__all__ = [
    "AFPacketMedium",
    "AFPacketMediumEthWifi",
    "CSMAPersistent",
    "LinkLayer",
    "FrameType",
    "LinkFrame",
    "FileTransfer",
    "FileTransferState",
    "ReliableTransfer",
    "PeerInfo",
    "PeerDiscoveryService",
    "MessageProtocol",
]

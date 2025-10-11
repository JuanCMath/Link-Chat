"""LinkChat: Peer-to-peer chat application over direct link-layer networking.

This package provides a complete chat application that communicates directly
over layer 2 (data link layer) using raw sockets, bypassing traditional TCP/IP
networking. It includes a PyQt6 GUI, file/folder transfer capabilities, and
automatic peer discovery.

Main Components:
    - backend: High-level facade for network operations
    - link: Low-level networking (CSMA, framing, file transfer, etc.)
    - app: PyQt6 GUI application

Example:
    >>> from linkchat.backend import LinkChatBackend
    >>> backend = LinkChatBackend(interface="eth0")
    >>> backend.start()
"""

__version__ = "1.0.0"
__author__ = "Link-Chat Team"

from .backend import LinkChatBackend
from .link.peer_discovery import PeerInfo

__all__ = ["LinkChatBackend", "PeerInfo"]

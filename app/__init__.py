"""
LinkChat Application Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A peer-to-peer messaging and file transfer system using raw Ethernet frames.

This package provides a complete P2P networking stack operating at Layer 2
(Data Link Layer) without requiring IP addresses or TCP/IP protocols.

Package Structure:
    - raw_socket: Low-level raw Ethernet socket handling
    - frame_helper: Frame encoding/decoding with CRC validation
    - service_threads: Multithreaded frame RX/TX/Dispatch coordination
    - peer_models: Data models for peer representation
    - peer_store: Persistence layer with Protocol pattern
    - peer_discovery: Automatic peer discovery via beacons
    - ack_protocol: ACK-based retry management
    - file_transfer: Reliable file and directory transfers
    - core/: Configuration and application facade
    - frontend/: User interface implementations

Key Features:
    - Layer 2 Ethernet communication (no IP required)
    - CRC16-CCITT error detection with bit stuffing
    - Automatic peer discovery via periodic beacons
    - Reliable message delivery with ACK retries
    - File and directory transfer with chunking
    - Directory transfers via tar.gz packaging
    - JSON-based peer persistence

Example Usage:
    >>> from app.core.config import load_config
    >>> from app.core.app_facade import LinkChatApp
    >>> from app.frontend.console import ConsoleFrontend
    >>> 
    >>> config = load_config()
    >>> app = LinkChatApp(config)
    >>> console = ConsoleFrontend(app)
    >>> console.run()

Architecture:
    The application follows a layered architecture:
    
    Frontend Layer (console.py)
         ↓
    Facade Layer (app_facade.py)
         ↓
    Service Layer (discovery, file_transfer, ack_protocol)
         ↓
    Transport Layer (service_threads.py)
         ↓
    Socket Layer (raw_socket.py)

Environment Variables:
    See core/config.py for full configuration options.
"""

__version__ = "2.0.0"
__author__ = "LinkChat Team"

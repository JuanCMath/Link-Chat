"""
LinkChat Application
~~~~~~~~~~~~~~~~~~~~

Peer-to-peer messaging and file transfer system over raw Ethernet.

LinkChat is a Layer 2 networking application that enables direct peer-to-peer
communication without IP addresses or TCP/IP stack dependencies. It operates
directly on Ethernet frames for maximum efficiency and minimal overhead.

Package Structure:
    backend/
        core/
            - raw_socket: Low-level Ethernet socket handling (AF_PACKET)
            - service_threads: Multithreaded RX/TX/Dispatch coordination
            - ack_protocol: Reliable delivery with automatic retries
            - file_transfer: File and directory transfer protocol (FTv2)
            - config: Environment-based configuration management

        peer_management/
            - peer_models: Dataclass definitions for peers
            - peer_store: JSON persistence layer
            - peer_registry: Thread-safe in-memory peer database
            - peer_discovery: Automatic beacon-based discovery

        utils/
            - frame_helper: CRC16-CCITT validation and bit stuffing
            - mac_utils: MAC address conversion and validation
            - services: Archive creation and helper utilities

        app_facade.py: High-level application facade

    frontend/
        console.py: Interactive command-line interface (REPL)

Key Features:
    - Layer 2 Ethernet communication (no IP required)
    - CRC16-CCITT error detection with bit stuffing
    - Automatic peer discovery via periodic beacons
    - Reliable message delivery with ACK retries
    - File and directory transfer with chunking
    - Directory transfers via tar.gz packaging
    - JSON-based peer persistence
    - Broadcast messaging to all peers
    - Graceful shutdown with peer notifications

Example Usage:
    >>> from app.backend.core.config import load_config
    >>> from app.backend.app_facade import LinkChatApp
    >>> from app.frontend.console import ConsoleFrontend
    >>> 
    >>> config = load_config()
    >>> app = LinkChatApp(config)
    >>> console = ConsoleFrontend(app)
    >>> console.run()

Architecture:
    The application follows a clean layered architecture:
    
    Frontend Layer (console.py)
         ↓
    Facade Layer (app_facade.py)
         ↓
    Service Layer (peer_discovery, file_transfer, ack_protocol)
         ↓
    Transport Layer (service_threads.py)
         ↓
    Socket Layer (raw_socket.py)
         ↓
    Socket Layer (raw_socket.py)

Environment Variables:
    See core/config.py for full configuration options.
"""

__version__ = "2.0.0"
__author__ = "LinkChat Team"

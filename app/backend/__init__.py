"""
LinkChat Backend Package
~~~~~~~~~~~~~~~~~~~~~~~~~

Backend infrastructure for peer-to-peer messaging and file transfer.

This package contains all the core networking, protocol, and peer management
components that power the LinkChat application. It operates at Layer 2
(Data Link Layer) using raw Ethernet frames without IP or TCP dependencies.

Package Structure:
    core/
        - raw_socket: Low-level raw Ethernet socket handling
        - service_threads: Multithreaded frame RX/TX/Dispatch coordination
        - ack_protocol: ACK-based retry management for reliable delivery
        - file_transfer: File and directory transfer protocol (FTv2)
        - config: Environment variable configuration management

    peer_management/
        - peer_models: Data models for peer representation
        - peer_store: JSON persistence layer with Protocol pattern
        - peer_registry: Thread-safe in-memory peer database
        - peer_discovery: Automatic beacon-based peer discovery

    utils/
        - frame_helper: Frame encoding/decoding with CRC validation
        - mac_utils: MAC address conversion and formatting utilities
        - services: Archive creation and MAC resolution helpers

    app_facade.py: High-level application facade coordinating all services

Key Features:
    - Layer 2 Ethernet communication (no IP required)
    - CRC16-CCITT error detection with bit stuffing
    - Automatic peer discovery via periodic beacons
    - Reliable message delivery with ACK retries
    - File and directory transfer with chunking
    - Directory transfers via tar.gz packaging
    - JSON-based peer persistence

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
    The backend follows a layered architecture:
    
    Application Facade (app_facade.py)
         ↓
    Service Layer (peer_discovery, file_transfer, ack_protocol)
         ↓
    Transport Layer (service_threads.py)
         ↓
    Socket Layer (raw_socket.py)
"""

__version__ = "2.0.0"
__author__ = "LinkChat Team"

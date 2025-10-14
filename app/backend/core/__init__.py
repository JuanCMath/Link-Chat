"""
Core Networking Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Low-level networking and protocol modules for LinkChat.

This package contains the fundamental building blocks for raw Ethernet
communication, frame processing, and reliable data transfer.

Modules:
    raw_socket: Raw Ethernet socket wrapper (AF_PACKET on Linux)
    service_threads: Multithreaded RX/TX/Dispatch frame coordination
    ack_protocol: ACK-based retry manager for reliable delivery
    file_transfer: File and directory transfer protocol (FTv2)
    config: Environment variable configuration management

Architecture:
    These modules form the transport and session layers of LinkChat,
    operating directly on Layer 2 Ethernet frames without IP dependencies.

Example:
    >>> from app.backend.core.raw_socket import SocketManager
    >>> from app.backend.core.service_threads import ThreadManager
    >>> 
    >>> sock = SocketManager("eth0", 0x88B5)
    >>> mgr = ThreadManager(sock, on_frame=handle_frame)
    >>> mgr.start()
"""

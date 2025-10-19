"""
app_facade.py
~~~~~~~~~~~~~

Application facade coordinating LinkChat backend services.

This module provides the LinkChatApp class, which acts as the primary
interface for frontend implementations (console, GUI, web). It orchestrates
all networking components, including raw sockets, peer discovery, file
transfers, and acknowledgment protocols.

Architecture:
    The facade pattern decouples presentation logic from networking logic,
    allowing multiple frontends to reuse the same backend infrastructure
    without duplicating network code.

Components Managed:
    - SocketManager: Raw Ethernet socket handling (core.raw_socket)
    - ThreadManager: Frame RX/TX/Dispatch coordination (core.service_threads)
    - PeerRegistry: Peer database with JSON persistence (peer_management.peer_registry)
    - PeerDiscovery: Automatic beacon-based discovery (peer_management.peer_discovery)
    - FTv2: File and directory transfer protocol (core.file_transfer)
    - AckRetryManager: Message acknowledgment and retries (core.ack_protocol)

Example:
    >>> from app.backend.core.config import load_config
    >>> from app.backend.app_facade import LinkChatApp
    >>> 
    >>> config = load_config()
    >>> app = LinkChatApp(config)
    >>> app.start()
    >>> app.send_chat("Hello world!")
    >>> app.stop()
"""

import os
import uuid
from typing import Callable, Dict, List, Optional

from .core.ack_protocol import ACK_KIND_DATA, ACK_KIND_MSG, AckRetryManager
from .core.file_transfer import FTv2
from .core.raw_socket import SocketManager
from .core.config import LinkChatConfig
from .core.service_threads import ThreadManager

from .peer_management.peer_discovery import PeerDiscovery
from .peer_management.peer_registry import PeerRegistry
from .peer_management.peer_models import Peer
from .peer_management.peer_store import JSONPeerStore

from .utils.services import (
    create_directory_archive,
    pop_pending_archive,
    resolve_mac,
    track_pending_archive
)
from .utils.mac_utils import (
    mac_bytes_to_str,
    mac_str_to_bytes
)


def _default_output(message: str) -> None:
    """
    Default output callback that prints to stdout with flush.

    Args:
        message: Text to display to the user.
    """
    print(message, flush=True)


class LinkChatApp:
    """
    High-level application facade coordinating LinkChat backend services.

    This class provides a simplified interface for frontends to interact with
    the LinkChat networking stack. It manages lifecycle, peer operations,
    messaging, and file transfers through a unified API.

    Responsibilities:
        - Initialize and manage all networking components
        - Coordinate message sending with ACK retries
        - Handle file and directory transfers
        - Track peer discovery state
        - Route incoming frames to appropriate handlers

    Attributes:
        config: Application configuration from environment variables.
        registry: PeerRegistry for discovered peers.
        discovery: PeerDiscovery instance (optional, can be stopped).
        ft: FTv2 file transfer manager (optional).
        msg_ack_mgr: AckRetryManager for chat message acknowledgments.

    Example:
        >>> config = LinkChatConfig(
        ...     iface="eth0",
        ...     name="Alice",
        ...     inbox_dir="/data/inbox"
        ... )
        >>> app = LinkChatApp(config)
        >>> app.start()
        >>> app.set_active_peer("aa:bb:cc:dd:ee:ff")
        >>> app.send_chat("Hello!")
        >>> app.stop()
    """

    def __init__(
        self,
        config: LinkChatConfig,
        *,
        output: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize application facade with configuration.

        Args:
            config: LinkChatConfig instance with all settings.
            output: Optional callback for status messages. Defaults to print().

        Example:
            >>> config = load_config()
            >>> app = LinkChatApp(config, output=lambda msg: logger.info(msg))
        """
        self.config = config
        self._output = output or _default_output

        self._store = JSONPeerStore(config.peers_file)
        self.registry = PeerRegistry(self._store, config.max_peer_age_secs)
        self.iface_registries: Dict[str, PeerRegistry] = {}
        self._current_iface = config.iface

        self._sock: Optional[SocketManager] = None
        self._mgr: Optional[ThreadManager] = None
        self.discovery: Optional[PeerDiscovery] = None
        self.ft: Optional[FTv2] = None
        self.msg_ack_mgr: Optional[AckRetryManager] = None
        self._running = False

        self._active_peer: Optional[bytes] = None

    # Lifecycle -----------------------------------------------------

    def start(self) -> None:
        """
        Initialize and start all backend services.

        This method performs the following startup sequence:
        1. Open raw Ethernet socket on configured interface
        2. Start ThreadManager for frame processing
        3. Load or reset peer database based on configuration
        4. Start PeerDiscovery beacon broadcasts
        5. Initialize FTv2 file transfer manager
        6. Start AckRetryManager for message acknowledgments

        Thread-safe: Can be called multiple times (no-op if already running).

        Example:
            >>> app.start()
            [init] peers loaded: 3
            [up] iface=eth0 mac=aa:bb:cc:dd:ee:ff ethertype=0x88b5 name=Alice
        """
        if self._running:
            return

        self._sock = SocketManager(self.config.iface, self.config.ethertype)
        self._mgr = ThreadManager(
            self._sock,
            on_frame=self._on_frame,
            drop_own_frames=True,
        )
        self._mgr.start()

        if self.config.reset_peers_on_start:
            self.registry.reset()
            self._emit(f"[init] peers reset ({self.config.peers_file})")
        else:
            count = self.registry.load()
            self._emit(f"[init] peers loaded: {count}")

        self.discovery = PeerDiscovery(
            mgr=self._mgr,
            name=self.config.name,
            registry=self.registry,
            interval=self.config.beacon_interval,
            on_beacon=self._on_beacon,
        )
        self.discovery.start()

        self.ft = FTv2(
            mgr=self._mgr,
            my_name=self.config.name,
            inbox_dir=self.config.inbox_dir,
            chunk_size=self.config.chunk_size,
            on_info=self._emit,
            on_progress=self._emit_progress,
            on_complete=self._ft_on_complete,
            on_ack=self._handle_ack,
            data_retry_interval=self.config.file_retry_interval,
            data_max_retries=self.config.file_max_retries,
        )

        self.msg_ack_mgr = AckRetryManager(
            "msg",
            self.config.msg_retry_interval,
            self.config.msg_max_retries,
        )
        self.msg_ack_mgr.start()

        mac_address = self._sock.get_mac_address()
        self._emit(
            f"[up] iface={self.config.iface} mac={mac_address} "
            f"ethertype={hex(self.config.ethertype)} name={self.config.name}"
        )
        self._emit(
            "Tip: /sendfile <MAC|Name> </local/path> (saved in /data/inbox on receiver)"
        )
        self._emit(
            "Tip: /senddir <MAC|Name> </local/dir> (replaces folder on receiver)"
        )

        self._running = True
        

    def stop(self) -> None:
        """
        Shut down all background services in reverse startup order.

        Cleanup sequence:
        1. Stop message ACK manager
        2. Shutdown file transfer manager
        3. Stop peer discovery beacons
        4. Stop frame processing threads
        5. Close raw socket

        Thread-safe: Can be called multiple times (no-op if not running).

        Example:
            >>> app.stop()
            # All threads terminated, socket closed
        """
        if not self._running:
            return

        self._quit()
        from time import sleep
        sleep(0.5) # Waiting for the messages to be sent

        if self.msg_ack_mgr:
            self.msg_ack_mgr.stop()
            self.msg_ack_mgr = None

        if self.ft:
            self.ft.shutdown()
            self.ft = None

        if self.discovery:
            self.discovery.stop()
            self.discovery = None

        if self._mgr:
            self._mgr.stop()
            self._mgr = None

        if self._sock:
            self._sock.close()
            self._sock = None

        self._running = False


        # Exiting -------------------------------------------------------
    def _quit(self) -> None:
        """Send notifying exit beacon

        Returns:
            _type_: _description_
        """
        if not self._mgr:
            return

        msg_id = uuid.uuid4().hex[:8]
        text = f"{self.config.name}: Exiting..."
        payload = f"LEAVE::{msg_id}::{text}".encode()

        try:
            self._mgr.send_broadcast_payload(payload)
            self._emit(f"[tx → all] {"Exiting..."}")
        except Exception as exc:
            return


    # Helpers -------------------------------------------------------

    def _emit(self, message: str) -> None:
        """
        Send status message to output callback.

        Args:
            message: Text to display to user.
        """
        self._output(message)

    def _on_beacon(self, peer: Peer) -> None:
        """
        Handle received beacon from peer discovery.

        Args:
            peer: Peer instance with MAC, name, and timestamp.
        """
        self._emit(f"[beacon rx] {peer.mac} -> {peer.name}")

    def _emit_progress(self, role: str, sid: str, done: int, total: int) -> None:
        """
        Display file transfer progress.

        Args:
            role: Transfer role ("tx" or "rx").
            sid: Session ID for the transfer.
            done: Bytes transferred so far.
            total: Total bytes to transfer.
        """
        percent = (done / total * 100.0) if total else 0.0
        self._emit(f"[{role} {sid}] {done}/{total} bytes ({percent:.1f}%)")

    # Accessors -----------------------------------------------------

    def get_mac_address(self) -> Optional[str]:
        """
        Get local MAC address as string.

        Returns:
            Optional[str]: MAC address (e.g., "aa:bb:cc:dd:ee:ff") or None if not started.
        """
        if self._sock:
            return self._sock.get_mac_address()
        return None

    def list_peers(self) -> List[Peer]:
        """
        List all discovered peers.

        Returns:
            List[Peer]: List of Peer instances from registry.

        Example:
            >>> peers = app.list_peers()
            >>> for p in peers:
            ...     print(f"{p.name} ({p.mac})")
        """
        return self.registry.list()

    def reset_peers(self) -> None:
        """
        Clear peer database and persistence file.

        Example:
            >>> app.reset_peers()
            # Peer table cleared
        """
        self.registry.reset()

    def load_peers(self) -> int:
        """
        Load peers from JSON persistence file.

        Returns:
            int: Number of peers loaded.

        Example:
            >>> count = app.load_peers()
            >>> print(f"Loaded {count} peers")
        """
        return self.registry.load()

    def resolve_mac(self, token: str) -> Optional[str]:
        """
        Resolve peer name or partial MAC to full MAC address.

        Args:
            token: Peer name or MAC address (partial or full).

        Returns:
            Optional[str]: Full MAC address if found, None otherwise.

        Example:
            >>> app.resolve_mac("Alice")
            'aa:bb:cc:dd:ee:ff'
            >>> app.resolve_mac("aa:bb")
            'aa:bb:cc:dd:ee:ff'
        """
        return resolve_mac(token, self.registry)

    def set_active_peer(self, mac_str: str) -> bool:
        """
        Set active peer for chat messages.

        Args:
            mac_str: MAC address in colon-separated format.

        Returns:
            bool: True if MAC is valid, False otherwise.

        Example:
            >>> app.set_active_peer("aa:bb:cc:dd:ee:ff")
            True
        """
        try:
            self._active_peer = mac_str_to_bytes(mac_str)
            return True
        except Exception:
            self._emit("[peer] Invalid MAC provided.")
            return False

    def active_peer_mac(self) -> Optional[str]:
        """
        Get currently active peer MAC address.

        Returns:
            Optional[str]: Active peer MAC or None if not set.
        """
        if self._active_peer is None:
            return None
        return mac_bytes_to_str(self._active_peer)

    def has_active_peer(self) -> bool:
        """
        Check if an active peer is currently set.

        Returns:
            bool: True if active peer is set, False otherwise.
        """
        return self._active_peer is not None

    # Discovery -----------------------------------------------------

    def set_discovery(self, enabled: bool) -> None:
        """
        Enable or disable peer discovery beacons.

        Args:
            enabled: True to start beacons, False to stop.

        Example:
            >>> app.set_discovery(False)
            [discover] Beacon stopped.
        """
        if not self.discovery:
            return
        if enabled:
            self.discovery.start()
            self._emit("[discover] Beacon started.")
        else:
            self.discovery.stop()
            self._emit("[discover] Beacon stopped.")

    
    # Sending -------------------------------------------------------

    def send_chat(self, line: str) -> Optional[str]:
        """
        Send chat message to active peer with ACK retry.

        Args:
            line: Text message to send (without prefix).

        Returns:
            Optional[str]: Message ID if sent successfully, None on error.

        Example:
            >>> msg_id = app.send_chat("Hello world!")
            [tx → aa:bb:cc:dd:ee:ff] Hello world!

        Note:
            Requires active peer to be set via set_active_peer().
        """
        if not self._mgr:
            self._emit("[err] transport not ready")
            return None
        if not self._active_peer:
            self._emit("[warn] No active peer. Use: /peer <MAC|Name>")
            return None

        msg_id = uuid.uuid4().hex[:8]
        text = f"{self.config.name}: {line}"
        payload = f"MSG::{msg_id}::{text}".encode()
        dst_bytes = self._active_peer
        meta = {"text": text, "peer": mac_bytes_to_str(dst_bytes)}

        if self.msg_ack_mgr:
            mgr = self._mgr

            def send_once(dst=dst_bytes, data=payload, mgr=mgr) -> None:
                if mgr is None:
                    return
                mgr.send_unicast_payload(dst, data)

            def fail_once(info: Dict) -> None:
                label = info.get("text", text)
                self._emit(
                    f"[fail] no ACK after {self.config.msg_max_retries} attempts ({label})"
                )

            def error_once(exc: Exception) -> None:
                self._emit(f"[retry] error resending {msg_id}: {exc}")

            self.msg_ack_mgr.add(
                msg_id,
                send_once,
                fail_fn=fail_once,
                meta=meta,
                error_fn=error_once,
            )
        else:
            try:
                self._mgr.send_unicast_payload(dst_bytes, payload)
            except Exception as exc:
                self._emit(f"[err] send failed ({exc})")
                return None

        self._emit(f"[tx → {mac_bytes_to_str(dst_bytes)}] {line}")
        return msg_id

    def send_file(self, mac_str: str, path: str) -> bool:
        """
        Send file to peer with automatic retries.

        Args:
            mac_str: Destination MAC address.
            path: Local file path to send.

        Returns:
            bool: True if transfer initiated, False on error.

        Example:
            >>> app.send_file("aa:bb:cc:dd:ee:ff", "/home/user/document.pdf")
            [tx sid=abc123] /home/user/document.pdf
        """
        if not self.ft:
            self._emit("[err] file-transfer not ready")
            return False
        try:
            dst_mac = mac_str_to_bytes(mac_str)
        except Exception:
            self._emit("[sendfile] Invalid MAC.")
            return False
        self.ft.send_file(dst_mac, path)
        return True

    def send_directory(self, mac_str: str, dir_path: str) -> bool:
        """
        Send directory to peer as tar.gz archive.

        The directory is packaged into a temporary .tar.gz file, sent to
        the peer, and automatically extracted on the receiver side. The
        receiver replaces any existing folder with the same name.

        Args:
            mac_str: Destination MAC address.
            dir_path: Local directory path to send.

        Returns:
            bool: True if transfer initiated, False on error.

        Example:
            >>> app.send_directory("aa:bb:cc:dd:ee:ff", "/home/user/project/")
            [senddir] sending project/ as project.tar.gz

        Note:
            Temporary archive is automatically cleaned up after transfer completes.
        """
        if not self.ft:
            self._emit("[err] file-transfer not ready")
            return False

        package = create_directory_archive(dir_path)
        if not package:
            return False

        archive_path = package["archive_path"]
        folder_name = package["folder_name"]
        archive_name = f"{folder_name}.tar.gz"

        try:
            dst_mac = mac_str_to_bytes(mac_str)
        except Exception:
            self._emit("[senddir] Invalid MAC.")
            try:
                os.remove(archive_path)
            except Exception:
                pass
            return False

        self._emit(f"[senddir] sending {folder_name}/ as {archive_name}")
        sid = self.ft.send_file(
            dst_mac,
            archive_path,
            display_name=archive_name,
            kind="dir",
            meta={"dir_name": folder_name},
        )
        if not sid:
            try:
                os.remove(archive_path)
            except Exception:
                pass
            return False

        track_pending_archive(sid, archive_path)
        return True
    
    def broadcast_chat(self, line: str) -> bool:
        """
        Broadcast chat message to all discovered peers.

        Args:
            line: Text message to broadcast.

        Returns:
            bool: True if broadcast initiated, False on error.

        Example:
            >>> app.broadcast_chat("Hello everyone!")
            [broadcast] Hello everyone!"""
        
        if not self._mgr:
            self._emit("[err] transport not ready")
            return False

        msg_id = uuid.uuid4().hex[:8]
        text = f"{self.config.name}: {line}"
        payload = f"BCAST::{msg_id}::{text}".encode()
        peers = self.registry.list()

        if not peers:
            self._emit("[warn] No peers available. Message may not be received")

        try:
            self._mgr.send_broadcast_payload(payload)
            self._emit(f"[tx → all] {line}")
        except Exception as exc:
            self._emit(f"[err] send to all failed ({exc})")
            return False

        return True



    def change_interface(self, iface: str) -> bool:
        if(self._sock and self._sock.change_interface(iface)):
            if(self._current_iface != iface):
                self.iface_registries[iface] = self.registry
                self.registry = self.iface_registries.get(iface, PeerRegistry(self._store, self.config.max_peer_age_secs))
                self._current_iface = iface
            return True
        
        return False
        


    # Internal callbacks -------------------------------------------

    def _on_frame(self, dst: bytes, src: bytes, payload: bytes) -> None:
        """
        Handle incoming Ethernet frame.

        Routes frame to appropriate handler:
        - File transfer protocol (FTv2) if TYPE_CTRL, TYPE_DATA, or TYPE_ACK
        - Peer discovery if beacon message
        - Chat message otherwise

        Args:
            dst: Destination MAC address (bytes).
            src: Source MAC address (bytes).
            payload: Frame payload (excluding Ethernet header).

        Note:
            This callback is invoked by ThreadManager's dispatch thread.
        """

        self.registry.upsert(mac = mac_bytes_to_str(src)) # updates peer last_seen timestamp (or inserts it)

        if self.ft and self.ft.handle_payload(src, payload):
            return

        if len(payload) >= 2 and (payload[0] == 0x7E or payload[-1] == 0x7E):
            from .utils.frame_helper import debug_inspect_frame

            debug_inspect_frame(payload)
            self._emit(f"[warn] 0x7E frame not handled by FT (len={len(payload)})")
            return

        text = payload.decode(errors="ignore")
        display = text
        msg_id: Optional[str] = None
        bcast = False

        if text.startswith("MSG::"):
            parts = text.split("::", 2)
            if len(parts) == 3:
                msg_id = parts[1]
                display = parts[2]

        elif text.startswith("BCAST::"):
            parts = text.split("::", 2)
            if len(parts) == 3:
                msg_id = parts[1]
                display = parts[2]
                bcast = True
        
        elif text.startswith("LEAVE::"):
            self.registry.remove_peer(mac_bytes_to_str(src))

            parts = text.split("::", 2)
            if len(parts) == 3:
                msg_id = parts[1]
                display = parts[2]
                bcast = True

        if self.discovery:
            self.discovery.handle_incoming(src, display) # tries to get name

        self._emit(f"[rx {mac_bytes_to_str(src)} → {"all" if bcast else mac_bytes_to_str(dst)}] {display}")

        if not bcast and msg_id and self.ft:
            self.ft.send_ack(src, {"kind": ACK_KIND_MSG, "id": msg_id})

    def _handle_ack(self, kind: str, src_mac: bytes, data: Dict) -> None:
        """
        Handle received acknowledgment frame.

        Args:
            kind: ACK type (ACK_KIND_MSG or ACK_KIND_DATA).
            src_mac: Source MAC address sending the ACK.
            data: ACK payload dictionary.

        Note:
            Called by FTv2 when ACK frame is received.
        """
        mac = mac_bytes_to_str(src_mac)


        if kind == ACK_KIND_MSG:
            mid = data.get("id")
            if mid and self.msg_ack_mgr:
                info = self.msg_ack_mgr.ack(mid)
                if info:
                    text = info.get("text", "")
                    self._emit(f"[ack {mac}] message confirmed ({text})")

        elif kind == ACK_KIND_DATA:
            sid = data.get("sid")
            seq = data.get("seq")
            if sid is not None and seq is not None:
                self._emit(f"[ack {mac}] data sid={sid} seq={seq}")

    def _ft_on_complete(self, role: str, sid: str, ok: bool) -> None:
        """
        Handle file transfer completion.

        Args:
            role: Transfer role ("tx" or "rx").
            sid: Session ID.
            ok: True if transfer completed successfully, False on failure.

        Note:
            Automatically cleans up temporary archives for directory transfers.
        """
        status = "OK" if ok else "FAIL"
        self._emit(f"[{role} {sid}] {status}")

        archive_path = pop_pending_archive(sid)
        if archive_path:
            try:
                os.remove(archive_path)
            except OSError as exc:
                self._emit(f"[senddir] cleanup failed for {archive_path}: {exc}")

    # Utilities -----------------------------------------------------

    def is_running(self) -> bool:
        """
        Check if application is currently running.

        Returns:
            bool: True if started, False otherwise.

        Example:
            >>> if app.is_running():
            ...     app.send_chat("Hello!")
        """
        return self._running
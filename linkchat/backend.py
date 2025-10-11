"""Backend controller for Link-Chat application.

Provides a unified interface to the Link-Chat networking subsystem, coordinating
the link layer, message protocol, and file transfer components. Automatically
selects adaptive protocol parameters based on detected network medium (Ethernet
vs Wi-Fi).

The backend abstracts AF_PACKET socket management, frame routing, hardware type
detection, and protocol parameter tuning. GUI applications interact exclusively
with this backend.
"""

import threading
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .constants import ETHERTYPE_DATA, ETHERTYPE_DISCOVERY
from .link.af_packet_medium_eth_wifi import AFPacketMediumEthWifi
from .link.link_layer import FrameType, LinkFrame, LinkLayer
from .link.message_protocol import MessageProtocol
from .link.file_transfer import FileTransfer
from .link.peer_discovery import PeerDiscoveryService, PeerInfo
from .link.adaptive_params import message_params_from_medium, file_params_from_medium


class LinkChatBackend:
    """Facade controller for Link-Chat networking subsystem.
    
    Coordinates all networking components and provides a simplified API for the
    GUI. Handles lifecycle management, adaptive parameter selection, and frame
    routing.
    
    Attributes:
        interface: Network interface name (e.g., "eth0", "wlan0").
        ethertype: Custom protocol identifier (e.g., 0x88B5).
        download_dir: Directory for saving received files.
        on_message_received: Optional callback(src_mac, text) for incoming messages.
        on_file_progress: Optional callback(filename, bytes_done, total) for progress.
        on_file_complete: Optional callback(filename, success) for completed transfers.
    """
    
    def __init__(
        self,
        interface: str,
        ethertype: int = ETHERTYPE_DATA,
        download_dir: str = "./downloads",
        node_name: Optional[str] = None,
    ) -> None:
        """Initialize the backend controller without starting networking.
        
        Creates the backend controller instance and sets up configuration
        parameters. The constructor creates the download directory if it doesn't exist and
        initializes all internal state variables to None. No network resources
        are allocated until start() is called.
        
        Args:
            interface: Network interface name to use for communication. Must be
                a valid Linux network interface (e.g., "eth0", "enp3s0", "wlan0").
                The interface must exist and be accessible to the current user.
            ethertype: Custom EtherType value for data protocol identification. Default
                is ETHERTYPE_DATA (0x88B5) within the experimental range. All Link-Chat
                instances must use the same EtherType to communicate.
            download_dir: Directory path for storing received files. Created
                automatically with parent directories if it doesn't exist. Relative
                paths are resolved from the current working directory.
            node_name: Optional display name for this node in peer discovery.
        
        Raises:
            OSError: If download directory cannot be created due to permission
                or filesystem errors.
        """
        self.interface = interface
        self.ethertype = ethertype
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.node_name = node_name
        
        # GUI callbacks (set these before calling start())
        self.on_message_received: Optional[Callable[[bytes, str], None]] = None
        self.on_file_progress: Optional[Callable[[str, int, int], None]] = None
        self.on_file_complete: Optional[Callable[[str, bool], None]] = None
        self.on_peer_available: Optional[Callable[[PeerInfo], None]] = None
        self.on_peer_expired: Optional[Callable[[PeerInfo], None]] = None
        
        # Internal components (initialized in start())
        self._medium: Optional[AFPacketMediumEthWifi] = None
        self._link_layer: Optional[LinkLayer] = None
        self._message_protocol: Optional[MessageProtocol] = None
        self._file_transfer: Optional[FileTransfer] = None
        self._peer_discovery: Optional[PeerDiscoveryService] = None
        
        self._lock = threading.Lock()
        self._running = False
    
    @property
    def is_running(self) -> bool:
        """Check if backend is currently active.
        
        Returns:
            True if backend is running, False otherwise.
        """
        return self._running
    
    @property
    def local_mac(self) -> Optional[bytes]:
        """Get the local MAC address.
        
        Returns:
            6-byte MAC address if running, None otherwise.
        """
        return self._link_layer.mac if self._link_layer else None
    
    @property
    def local_mac_str(self) -> Optional[str]:
        """Get the local MAC address as string.
        
        Returns:
            MAC address in format "aa:bb:cc:dd:ee:ff" if running, None otherwise.
        """
        mac = self.local_mac
        return ":".join(f"{b:02x}" for b in mac) if mac else None
    
    @property
    def is_wifi(self) -> bool:
        """Check if interface is Wi-Fi.
        
        Returns:
            True if Wi-Fi (hatype == 801), False for Ethernet or if not running.
        """
        if not self._medium:
            return False
        return self._medium.hatype == 801
    
    def start(self) -> None:
        """Initialize and start all networking components.
        
        Creates the medium, link layer, and protocol layers with adaptive parameters
        based on detected hardware type (Ethernet vs Wi-Fi). Starts background
        receive thread for incoming frames.
        
        Raises:
            RuntimeError: If already running.
            OSError: If interface doesn't exist or permissions insufficient.
        """
        with self._lock:
            if self._running:
                raise RuntimeError("Backend already running")
            
            # Create link layer
            self._link_layer = LinkLayer(
                iface=self.interface,
                ethertype=self.ethertype,
                on_frame=self._on_frame_received,
                filter_ethertype=True,
            )
            self._medium = self._link_layer.medium
            
            # Get adaptive parameters for medium
            msg_params = message_params_from_medium(self._medium)
            file_params = file_params_from_medium(self._medium)
            
            # Create message protocol with adaptive params
            self._message_protocol = MessageProtocol(
                link_layer=self._link_layer,
                on_message=self._on_message_callback,
                max_payload=msg_params.max_payload,
                ack_timeout=msg_params.ack_timeout,
                max_retries=msg_params.max_retries,
                inter_part_delay=msg_params.inter_part_delay,
            )
            
            # Create file transfer with adaptive params
            self._file_transfer = FileTransfer(
                link_layer=self._link_layer,
                download_dir=str(self.download_dir),
                on_progress=self._on_file_progress_callback,
                on_complete=self._on_file_complete_callback,
                chunk_size=file_params.chunk_size,
                ack_timeout=file_params.ack_timeout,
                max_retries=file_params.max_retries,
                inter_chunk_delay=file_params.inter_chunk_delay,
            )
            
            # Create peer discovery service on separate EtherType
            self._peer_discovery = PeerDiscoveryService(
                interface=self.interface,
                ethertype=ETHERTYPE_DISCOVERY,
                display_name=self.node_name,
                on_peer_available=self._on_peer_available_callback,
                on_peer_expired=self._on_peer_expired_callback,
            )
            
            # Start listening for incoming frames
            self._link_layer.start_listening()
            self._peer_discovery.start()
            
            self._running = True
    
    def stop(self) -> None:
        """Stop all networking and clean up resources."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            
            if self._peer_discovery:
                self._peer_discovery.stop()
                self._peer_discovery = None
            
            if self._link_layer:
                self._link_layer.stop()
                self._link_layer = None
            
            if self._medium:
                self._medium.close()
                self._medium = None
            
            self._message_protocol = None
            self._file_transfer = None
    
    # ------------------------------------------------------------------
    # Public API for GUI
    # ------------------------------------------------------------------
    
    def send_message(self, dst_mac: bytes, text: str) -> bool:
        """Send a text message to destination MAC address.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            text: Message text to send (UTF-8 encoded).
        
        Returns:
            True if message was acknowledged, False on failure.
        
        Raises:
            RuntimeError: If backend not running.
        """
        if not self._running or not self._message_protocol:
            raise RuntimeError("Backend not running")
        
        return self._message_protocol.send_message(dst_mac, text)
    
    def send_file(self, dst_mac: bytes, filepath: str) -> bool:
        """Send a file to destination MAC address.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            filepath: Path to file to send.
        
        Returns:
            True if file was successfully transferred, False on failure.
        
        Raises:
            RuntimeError: If backend not running.
            FileNotFoundError: If file doesn't exist.
        """
        if not self._running or not self._file_transfer:
            raise RuntimeError("Backend not running")
        
        return self._file_transfer.send_file(dst_mac, filepath)

    def send_folder(self, dst_mac: bytes, folder_path: str) -> bool:
        """Send a complete folder to destination MAC address.
        
        Sends an entire directory tree by:
        1. Sending TRANSFER_META frame with JSON metadata listing all files.
        2. Waiting for metadata ACK confirmation from receiver.
        3. Sequentially sending each file via FileTransfer with virtual paths.
        
        The receiver reconstructs the directory structure based on metadata
        before files arrive, ensuring proper hierarchy preservation. Metadata
        ACK ensures the receiver is ready before file transmission begins.
        
        Args:
            dst_mac: Destination MAC address (6 bytes).
            folder_path: Path to the folder to send.
        
        Returns:
            True if all files were successfully transferred, False on any failure.
        
        Raises:
            RuntimeError: If backend not running.
            NotADirectoryError: If folder_path is not a directory.
        """
        if not self._running or not self._file_transfer:
            raise RuntimeError("Backend not running")
        return self._file_transfer.send_folder(dst_mac, folder_path)
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get current network configuration and status.
        
        Returns:
            Dictionary with keys: interface, mac_address, medium_type, 
            ethertype, running.
        """
        return {
            "interface": self.interface,
            "mac_address": self.local_mac_str,
            "medium_type": "wifi" if self.is_wifi else "ethernet",
            "ethertype": f"0x{self.ethertype:04x}",
            "running": self._running,
        }
    
    # ------------------------------------------------------------------
    # Internal frame routing
    # ------------------------------------------------------------------
    
    def _on_frame_received(self, frame: LinkFrame) -> None:
        """Route incoming frames to appropriate protocol handlers.
        
        Called by LinkLayer when a frame is received. Dispatches to
        MessageProtocol or FileTransfer based on frame type.
        
        Frame routing logic:
        - MESSAGE frames: Routed to MessageProtocol for reassembly.
        - ACK frames: Routed to BOTH MessageProtocol AND FileTransfer since
          both protocols use ACKs with different payload formats. Each handler
          validates the ACK format and ignores irrelevant ACKs.
        - TRANSFER_META, FILE_CHUNK frames: Routed to FileTransfer for file/folder reception.
        """
        if frame.typ == FrameType.MESSAGE:
            if self._message_protocol:
                self._message_protocol.handle_frame(frame)
        elif frame.typ == FrameType.ACK:
            # ACK frames must be routed to both message and file protocols
            # since both use ACKs with different payload formats
            if self._message_protocol:
                self._message_protocol.handle_frame(frame)
            if self._file_transfer:
                self._file_transfer.handle_received_frame(frame)
        elif frame.typ in (FrameType.TRANSFER_META, FrameType.FILE_CHUNK):
            if self._file_transfer:
                self._file_transfer.handle_received_frame(frame)
    
    # ------------------------------------------------------------------
    # Callbacks to GUI
    # ------------------------------------------------------------------
    
    def _on_message_callback(self, src_mac: bytes, text: str) -> None:
        """Internal callback when message is received and decoded."""
        if self.on_message_received:
            self.on_message_received(src_mac, text)
    
    def _on_file_progress_callback(self, filename: str, bytes_done: int, total: int) -> None:
        """Internal callback for file transfer progress."""
        if self.on_file_progress:
            self.on_file_progress(filename, bytes_done, total)
    
    def _on_file_complete_callback(self, filename: str, success: bool) -> None:
        """Internal callback when file transfer completes."""
        if self.on_file_complete:
            self.on_file_complete(filename, success)
    
    def _on_peer_available_callback(self, peer: PeerInfo) -> None:
        """Internal callback when a new peer is discovered."""
        if self.on_peer_available:
            self.on_peer_available(peer)
    
    def _on_peer_expired_callback(self, peer: PeerInfo) -> None:
        """Internal callback when a peer times out."""
        if self.on_peer_expired:
            self.on_peer_expired(peer)
    
    # ------------------------------------------------------------------
    # Peer discovery utilities
    # ------------------------------------------------------------------
    
    def list_peers(self):
        """Get list of currently discovered peers.
        
        Returns:
            List of PeerInfo objects if running, empty list otherwise.
        """
        if not self._running or not self._peer_discovery:
            return []
        return self._peer_discovery.list_peers()
    
    def add_service(self, service_name: str) -> None:
        """Advertise an additional service capability.
        
        Args:
            service_name: Service identifier (e.g., 'chat', 'file-transfer').
        """
        if self._peer_discovery:
            self._peer_discovery.add_service(service_name)
    
    def remove_service(self, service_name: str) -> None:
        """Stop advertising a service capability.
        
        Args:
            service_name: Service identifier to remove.
        """
        if self._peer_discovery:
            self._peer_discovery.remove_service(service_name)
    
    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    
    @staticmethod
    def mac_str_to_bytes(mac: str) -> bytes:
        """Convert MAC address string to bytes.
        
        Args:
            mac: MAC address string ("aa:bb:cc:dd:ee:ff").
        
        Returns:
            6-byte MAC address.
        """
        return bytes(int(part, 16) for part in mac.split(":"))
    
    @staticmethod
    def mac_bytes_to_str(mac: bytes) -> str:
        """Convert MAC address bytes to string.
        
        Args:
            mac: 6-byte MAC address.
        
        Returns:
            MAC address string ("aa:bb:cc:dd:ee:ff").
        """
        return ":".join(f"{b:02x}" for b in mac)

"""Protocol constants for Link-Chat.

Defines EtherType values and other protocol-level constants used across the
Link-Chat application.
"""

# EtherType assignments (experimental range 0x88B5-0x88B7)
ETHERTYPE_DATA = 0x88B5      # Main data channel (messages, file transfers)
ETHERTYPE_DISCOVERY = 0x88B6  # Peer discovery beacon channel

# MAC address constants
BROADCAST_MAC = b"\xff" * 6   # IEEE 802.3 broadcast address (ff:ff:ff:ff:ff:ff)

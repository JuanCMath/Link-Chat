#!/usr/bin/env python3
"""Test AF_PACKET socket on eth0 interface."""
import socket
import sys

AF_PACKET = 17

try:
    print("Creating AF_PACKET socket...")
    s = socket.socket(AF_PACKET, socket.SOCK_RAW, socket.htons(0x88B5))
    
    print("Binding to eth0...")
    s.bind(("eth0", 0))
    
    print("✅ Socket created and bound successfully!")
    print(f"   Interface: eth0")
    print(f"   EtherType: 0x88B5")
    
    s.close()
    print("Socket closed.")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

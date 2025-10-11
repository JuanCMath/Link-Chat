#!/usr/bin/env python3
"""Test AF_PACKET socket on loopback interface."""
import socket
import sys
import select

AF_PACKET = 17

try:
    print("Testing loopback interface 'lo'...")
    print("Creating AF_PACKET socket...")
    s = socket.socket(AF_PACKET, socket.SOCK_RAW, socket.htons(0x88B5))
    
    print("Binding to lo...")
    s.bind(("lo", 0))
    
    print("✅ Socket created and bound successfully!")
    
    # Test receiving
    print("\nTesting receive with timeout...")
    s.settimeout(2.0)
    
    try:
        print("Waiting for packets (2 second timeout)...")
        ready = select.select([s], [], [], 2.0)
        if ready[0]:
            data, addr = s.recvfrom(65535)
            print(f"✅ Received {len(data)} bytes")
        else:
            print("⏱️  Timeout - no packets received (this is OK for loopback)")
    except socket.timeout:
        print("⏱️  Socket timeout (this is OK)")
    except OSError as e:
        print(f"❌ OSError during receive: {e}")
        print(f"   Error number: {e.errno}")
        sys.exit(1)
    
    s.close()
    print("\n✅ Loopback test passed!")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

#!/usr/bin/env python3
"""
Test script for Link-Chat communication between containers.
Run this inside a container to send test messages and files.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, '/app')

from linkchat.backend import LinkChatBackend
from linkchat.constants import ETHERTYPE_DATA


def get_mac_address(interface: str = "eth0") -> str:
    """Get MAC address of specified interface."""
    import subprocess
    try:
        result = subprocess.run(
            ["ip", "link", "show", interface],
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.split('\n'):
            if 'link/ether' in line:
                mac = line.split()[1]
                return mac
    except Exception as e:
        print(f"Error getting MAC: {e}")
    return "00:00:00:00:00:00"


def main():
    """Run interactive test session."""
    print("=" * 60)
    print("Link-Chat Container Test Script")
    print("=" * 60)
    
    interface = "eth0"
    mac = get_mac_address(interface)
    print(f"\n📡 Interface: {interface}")
    print(f"🏷️  MAC Address: {mac}")
    
    # Create backend
    print(f"\n🚀 Starting Link-Chat backend...")
    backend = LinkChatBackend(
        interface=interface,
        ethertype=ETHERTYPE_DATA,
        download_dir="/app/downloads",
        node_name=None  # Will be set from environment
    )
    
    # Set up callbacks
    def on_message(src_mac: bytes, text: str):
        print(f"\n📨 Message from {src_mac.hex(':')}: {text}")
    
    def on_file_progress(filename: str, done: int, total: int):
        percent = (done / total * 100) if total > 0 else 0
        print(f"📦 {filename}: {done}/{total} bytes ({percent:.1f}%)")
    
    def on_file_complete(filename: str, success: bool):
        status = "✅ Success" if success else "❌ Failed"
        print(f"📁 {filename}: {status}")
    
    backend.on_message_received = on_message
    backend.on_file_progress = on_file_progress
    backend.on_file_complete = on_file_complete
    
    # Start backend
    try:
        backend.start()
        print(f"✅ Backend started successfully!")
    except Exception as e:
        print(f"❌ Failed to start backend: {e}")
        return 1
    
    # Interactive menu
    print("\n" + "=" * 60)
    print("Commands:")
    print("  1. Send message")
    print("  2. Send file")
    print("  3. List network interfaces")
    print("  4. Show backend info")
    print("  5. Create test file")
    print("  q. Quit")
    print("=" * 60)
    
    try:
        while True:
            cmd = input("\n> ").strip()
            
            if cmd == 'q':
                break
            
            elif cmd == '1':
                dst_mac_str = input("Destination MAC (xx:xx:xx:xx:xx:xx): ").strip()
                message = input("Message: ").strip()
                
                try:
                    dst_mac = bytes.fromhex(dst_mac_str.replace(':', ''))
                    if backend.send_message(dst_mac, message):
                        print("✅ Message sent!")
                    else:
                        print("❌ Failed to send message")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            elif cmd == '2':
                dst_mac_str = input("Destination MAC (xx:xx:xx:xx:xx:xx): ").strip()
                filepath = input("File path: ").strip()
                
                try:
                    dst_mac = bytes.fromhex(dst_mac_str.replace(':', ''))
                    if backend.send_file(dst_mac, filepath):
                        print("✅ File sent!")
                    else:
                        print("❌ Failed to send file")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            elif cmd == '3':
                import subprocess
                result = subprocess.run(["ip", "link", "show"], capture_output=True, text=True)
                print(result.stdout)
            
            elif cmd == '4':
                info = backend.get_network_info()
                print(f"\nInterface: {info['interface']}")
                print(f"MAC: {info['mac_address']}")
                print(f"Medium: {info['medium_type']}")
                print(f"EtherType: 0x{info['ethertype']:04x}")
                print(f"Running: {info['running']}")
            
            elif cmd == '5':
                filename = input("Filename: ").strip() or "test.txt"
                size = input("Size in KB (default 10): ").strip() or "10"
                
                try:
                    size_bytes = int(size) * 1024
                    filepath = Path("/app") / filename
                    filepath.write_bytes(b"X" * size_bytes)
                    print(f"✅ Created {filepath} ({size_bytes} bytes)")
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            else:
                print("❓ Unknown command")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    
    finally:
        print("\n🛑 Stopping backend...")
        backend.stop()
        print("👋 Goodbye!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

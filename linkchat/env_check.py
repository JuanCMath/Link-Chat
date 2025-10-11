"""Network capability detection and environment guidance.

This module helps detect the runtime environment and provides guidance
on how to enable network access for Link-Chat's raw packet operations.
"""
import os
import platform
import socket
import sys
from typing import Optional, Tuple


def is_running_in_docker() -> bool:
    """Check if the process is running inside a Docker container.
    
    Returns:
        True if running in Docker, False otherwise.
    """
    # Check for .dockerenv file
    if os.path.exists('/.dockerenv'):
        return True
    
    # Check cgroup for docker
    try:
        with open('/proc/1/cgroup', 'r') as f:
            return 'docker' in f.read()
    except (FileNotFoundError, PermissionError):
        return False


def is_running_in_wsl() -> bool:
    """Check if the process is running inside WSL.
    
    Returns:
        True if running in WSL, False otherwise.
    """
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def is_using_macvlan() -> bool:
    """Check if the container is using MACVLAN networking.
    
    Returns:
        True if MACVLAN network is detected, False otherwise.
    """
    if not is_running_in_docker():
        return False
    
    try:
        # Check if eth0 has a MAC address that differs from default Docker bridge
        # MACVLAN gives the container its own unique MAC on the physical network
        with open('/sys/class/net/eth0/address', 'r') as f:
            mac = f.read().strip()
            # Docker bridge typically uses 02:42:xx:xx:xx:xx
            # MACVLAN will use the host's MAC prefix or a unique one
            return not mac.startswith('02:42:')
    except FileNotFoundError:
        return False


def get_mac_address(interface: str) -> Optional[str]:
    """Get the MAC address of a network interface.
    
    Args:
        interface: Interface name (e.g., "eth0", "wlan0").
    
    Returns:
        MAC address as string, or None if not available.
    """
    try:
        with open(f'/sys/class/net/{interface}/address', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def can_use_af_packet() -> Tuple[bool, Optional[str]]:
    """Check if AF_PACKET sockets can be created.
    
    Returns:
        (success, error_message) tuple.
    """
    try:
        # Try to create an AF_PACKET socket
        AF_PACKET = getattr(socket, "AF_PACKET", 17)
        test_sock = socket.socket(AF_PACKET, socket.SOCK_RAW, 0)
        test_sock.close()
        return True, None
    except PermissionError:
        return False, "Permission denied - need CAP_NET_RAW capability or root"
    except OSError as e:
        return False, f"AF_PACKET not available: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def get_environment_info() -> dict:
    """Get comprehensive environment information.
    
    Returns:
        Dictionary with environment details.
    """
    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'in_docker': is_running_in_docker(),
        'in_wsl': is_running_in_wsl(),
        'using_macvlan': is_using_macvlan(),
        'python_version': sys.version,
    }


def print_network_guidance() -> None:
    """Print guidance for enabling network access based on environment."""
    env = get_environment_info()
    can_af_packet, af_error = can_use_af_packet()
    
    print("=" * 70)
    print("Link-Chat Network Environment Check")
    print("=" * 70)
    print()
    
    print(f"Platform: {env['platform']} {env['platform_release']}")
    print(f"Running in Docker: {env['in_docker']}")
    print(f"Running in WSL: {env['in_wsl']}")
    print(f"Using MACVLAN: {env['using_macvlan']}")
    print(f"AF_PACKET available: {can_af_packet}")
    if not can_af_packet:
        print(f"  Error: {af_error}")
    print()
    
    # Provide guidance based on environment
    if env['platform'] == 'Linux':
        if env['in_docker']:
            print("🐳 DOCKER CONTAINER DETECTED")
            print()
            
            if env['using_macvlan']:
                print("🌐 MACVLAN NETWORKING ACTIVE")
                print()
                # Show MAC address for eth0 (the MACVLAN interface)
                mac = get_mac_address('eth0')
                if mac:
                    print(f"📧 Container MAC Address: {mac}")
                    print()
                    print("✅ Layer 2 Operation Ready!")
                    print()
                    print("Your container has a unique MAC address on the physical network.")
                    print("Link-Chat will communicate using Ethernet frames (Layer 2).")
                    print()
                    print("🔍 Key Points:")
                    print("  • Use interface 'eth0' in Link-Chat GUI")
                    print("  • IP addresses are for Docker management only")
                    print("  • Link-Chat operates purely at Layer 2 (MAC addresses)")
                    print("  • You can communicate with:")
                    print("    - Other containers on the same MACVLAN network")
                    print("    - Physical machines on the same network segment")
                    print()
                    if can_af_packet:
                        print("✅ AF_PACKET sockets are available!")
                    else:
                        print("⚠️  AF_PACKET check failed, but should work with NET_RAW capability")
            elif can_af_packet:
                print("✅ AF_PACKET sockets are available!")
                print()
                print("You're likely running with --network host and proper capabilities.")
                print("You should be able to use real network interfaces.")
            else:
                print("❌ AF_PACKET sockets are NOT available")
                print()
                print("🔧 Recommended: Use MACVLAN Networking")
                print()
                print("MACVLAN gives your container a unique MAC address on the physical")
                print("network, enabling true Layer 2 communication.")
                print()
                print("Setup Steps:")
                print("  1. Run the setup script:")
                print("     ./docker/setup-macvlan.sh")
                print()
                print("  2. Start Link-Chat with MACVLAN:")
                print("     ./docker/run-macvlan.sh")
                print()
                print("Alternative: --network host mode")
                print("  docker run -it --rm --network host \\")
                print("    --cap-add=NET_ADMIN --cap-add=NET_RAW \\")
                print("    linkchat-interactive python -m linkchat.app.qt_main")
                print()
                print("Note: --network host only works on Linux, not Docker Desktop")
        
        elif env['in_wsl']:
            print("🪟 WSL DETECTED")
            print()
            if can_af_packet:
                print("✅ AF_PACKET sockets are available!")
                print()
                print("You can use real network interfaces in WSL.")
                print("Available interfaces: run 'ip link show'")
            else:
                print("❌ AF_PACKET sockets require root or capabilities")
                print()
                print("Solutions:")
                print("  1. Run with sudo: sudo python -m linkchat.app.qt_main")
                print("  2. Set capabilities: sudo setcap cap_net_raw+ep $(which python)")
        
        else:
            print("🐧 NATIVE LINUX DETECTED")
            print()
            if can_af_packet:
                print("✅ AF_PACKET sockets are available!")
                print()
                print("Your system is ready for raw packet operations.")
            else:
                print("❌ AF_PACKET sockets require root or capabilities")
                print()
                print("Solutions:")
                print("  1. Run with sudo: sudo python -m linkchat.app.qt_main")
                print("  2. Set capabilities: sudo setcap cap_net_raw+ep $(which python)")
    
    elif env['platform'] == 'Windows':
        print("🪟 WINDOWS DETECTED")
        print()
        print("❌ Windows does not support AF_PACKET sockets")
        print()
        print("Solutions:")
        print("  1. Use WSL2 (recommended):")
        print("     wsl")
        print("     cd /mnt/d/path/to/project")
        print("     python -m linkchat.app.qt_main")
        print()
        print("  2. Run on Linux VM or Docker on Linux host")
        print()
        print("  3. For testing only: use loopback interface 'lo' in Docker")
    
    elif env['platform'] == 'Darwin':
        print("🍎 MACOS DETECTED")
        print()
        print("❌ macOS has limited AF_PACKET support")
        print()
        print("Solutions:")
        print("  1. Use Linux VM")
        print("  2. Use Docker on Linux host")
        print("  3. Try BPF (Berkeley Packet Filter) - requires code changes")
    
    print()
    print("=" * 70)


def check_interface_exists(interface: str) -> bool:
    """Check if a network interface exists.
    
    Args:
        interface: Interface name (e.g., "eth0", "wlan0").
    
    Returns:
        True if interface exists, False otherwise.
    """
    try:
        with open(f'/sys/class/net/{interface}/ifindex', 'r') as f:
            return True
    except FileNotFoundError:
        return False


def list_available_interfaces() -> list[str]:
    """List all available network interfaces.
    
    Returns:
        List of interface names.
    """
    try:
        import os
        return [iface for iface in os.listdir('/sys/class/net/') 
                if iface != 'lo' or True]  # Include loopback for testing
    except FileNotFoundError:
        return []


if __name__ == '__main__':
    # Run environment check
    print_network_guidance()
    print()
    
    # List available interfaces
    interfaces = list_available_interfaces()
    if interfaces:
        print("Available network interfaces:")
        for iface in interfaces:
            print(f"  - {iface}")
    else:
        print("Could not list network interfaces")

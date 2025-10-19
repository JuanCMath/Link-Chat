import os
from typing import List

def list_network_interfaces(exclude_virtual: bool = True) -> List[str]:

    try:
        interfaces = os.listdir('/sys/class/net')
    except NotADirectoryError:
        return []

    if exclude_virtual:
        interfaces = [i for i in interfaces if i not in ('lo', 'docker0')]

    return interfaces

def is_iface_down(iface: str) -> bool:
    try:
        with open (f'/sys/class/net/{iface}/operstate', 'r') as f:
            return f.read().strip().lower() == 'down'
        
    except Exception:
        return True
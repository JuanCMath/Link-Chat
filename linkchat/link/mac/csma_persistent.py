"""CSMA/CD persistent medium access control.

Provides a generic CSMA (Carrier Sense Multiple Access) implementation that is
independent of the physical medium. The caller provides carrier sense and
transmission functions, and this module handles the collision avoidance logic.
"""

import time
from typing import Callable

class CSMAPersistent:
    """CSMA/CD persistent medium access controller.
    
    Implements carrier sense multiple access with collision detection using
    a persistent strategy: when the medium is busy, continuously monitor until
    it becomes free, then transmit immediately.
    """
    
    def __init__(self, sense_func: Callable[[float], bool], send_func: Callable[[bytes], None],
                 difs: float = 0.01):
        """Initialize the CSMA controller.
        
        Args:
            sense_func: Callable that listens for 'difs' seconds and returns True
                        if the channel is idle.
            send_func: Callable that transmits data bytes to the medium.
            difs: Distributed Inter-Frame Space in seconds (carrier sense duration).
        """
        self.sense_func = sense_func
        self.send_func = send_func
        self.difs = difs

    def send(self, data: bytes):
        """Send data using CSMA/CD persistent strategy.
        
        Implements the persistent CSMA algorithm:
        1. Sense the channel for the DIFS period.
        2. If idle, transmit immediately.
        3. If busy, continue sensing (persistent) until the channel is free.
        
        No random backoff is applied; the method blocks until transmission succeeds.
        
        Args:
            data: Bytes to transmit.
        """
        while True:
            channel_free = self.sense_func(self.difs)
            if channel_free:
                self.send_func(data)
                return
            time.sleep(self.difs * 0.25)



    @staticmethod
    def make_sense_with_recv_once(recv_once_callable):
        """Create a carrier sense function from a receive-once callable.
        
        Constructs a sense_func compatible with CSMAPersistent by polling a
        recv_once callable. The channel is considered busy if any data arrives
        during the sensing period.
        
        Args:
            recv_once_callable: Callable with signature (timeout: float) -> bytes | None.
                                Returns received data or None if nothing arrives.
        
        Returns:
            A sense_func(difs: float) -> bool that returns True if the channel
            is idle for the entire DIFS period.
        """
        def sense_func(difs: float) -> bool:
            end = time.time() + difs
            while time.time() < end:
                remaining = max(0.0, end - time.time())
                payload = recv_once_callable(timeout=remaining)
                if payload is not None:
                    return False
            return True
        return sense_func

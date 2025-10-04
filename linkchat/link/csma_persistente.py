# csma_persistente.py
# CSMA persistente genérico: independiente del medio.
# Tú provees dos callables:
#   - sense_func(difs: float) -> bool     # True si el canal está LIBRE tras escuchar 'difs' seg.
#   - send_func(data: bytes) -> None      # Envía los bytes por el medio elegido.

import time
from typing import Callable

class CSMAPersistente:
    def __init__(self, sense_func: Callable[[float], bool], send_func: Callable[[bytes], None],
                 difs: float = 0.01):
        """
        sense_func(difs) -> bool: escucha 'difs' segundos y retorna True si el canal está LIBRE.
        send_func(data): envía los datos por el medio.
        """
        self.sense_func = sense_func
        self.send_func = send_func
        self.difs = difs

    def send(self, data: bytes):
        """
        CSMA persistente:
        1) Escuchar canal
        2) Si libre -> transmitir inmediatamente
        3) Si ocupado -> seguir esperando (persistente) hasta que se libere
        """
        while True:
            channel_free = self.sense_func(self.difs)
            if channel_free:
                self.send_func(data)
                return  # enviado
            # Persistente: no hace backoff aleatorio; simplemente sigue escuchando.
            # Opcionalmente, evita busy-wait muy cerrado:
            time.sleep(self.difs * 0.25)



    @staticmethod
    def make_sense_with_recv_once(recv_once_callable):
        """
        recv_once_callable(timeout: float) -> (payload: bytes|None)
        Devuelve None si no llegó nada; bytes si llegó algo.
        """
        def sense_func(difs: float) -> bool:
            end = time.time() + difs
            while time.time() < end:
                remaining = max(0.0, end - time.time())
                payload = recv_once_callable(timeout=remaining)
                if payload is not None:
                    # Hubo tráfico -> canal ocupado
                    return False
            return True  # no llegó nada -> libre
        return sense_func

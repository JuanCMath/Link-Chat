"""Console-based frontend for interacting with LinkChatApp."""

import sys
import time

from ..core.app_facade import LinkChatApp


class ConsoleFrontend:
    """Minimal console UI that delegates operations to LinkChatApp."""

    def __init__(self, app: LinkChatApp) -> None:
        self.app = app

    def run(self) -> None:
        """Run interactive loop; blocks until interrupted."""
        self.app.start()
        self.print_help()

        try:
            if sys.stdin.isatty():
                self._interactive_loop()
            else:
                self._receive_only()
        finally:
            self.app.stop()

    # Command loop -------------------------------------------------

    def _interactive_loop(self) -> None:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                print("[info] STDIN closed; receive-only mode.", flush=True)
                self._receive_only()
                return

            if not line:
                continue

            if line == "/help":
                self.print_help()
                continue

            if self._handle_command(line):
                continue

            self.app.send_chat(line)

    def _handle_command(self, line: str) -> bool:
        if line == "/me":
            mac = self.app.get_mac_address()
            if mac:
                print(f"[me] {mac} ({self.app.config.name})", flush=True)
            return True

        if line == "/peers":
            rows = self.app.list_peers()
            if not rows:
                print("[peers] (empty)", flush=True)
            else:
                for p in rows:
                    print(
                        f"  {p.mac}\t{p.name or '(?)'}\t{p.last_seen}",
                        flush=True,
                    )
            return True

        if line == "/peers reset":
            self.app.reset_peers()
            print("[peers] table and file cleared.", flush=True)
            return True

        if line.startswith("/peer "):
            token = line.split(" ", 1)[1].strip()
            mac_str = self.app.resolve_mac(token)
            if not mac_str:
                print(f"[peer] Not found '{token}'. Use /peers.", flush=True)
                return True
            if self.app.set_active_peer(mac_str):
                print(f"[peer] active destination = {mac_str}", flush=True)
            return True

        if line.startswith("/discover "):
            arg = line.split(" ", 1)[1].strip().lower()
            if arg == "off":
                self.app.set_discovery(False)
            elif arg == "on":
                self.app.set_discovery(True)
            else:
                print("[discover] Use: /discover on | /discover off", flush=True)
            return True

        if line.startswith("/sendfile "):
            parts = line.split(" ", 2)
            if len(parts) != 3:
                print("[sendfile] usage: /sendfile <MAC|Name> </local/path>", flush=True)
                return True
            token, path = parts[1], parts[2]
            mac_str = self.app.resolve_mac(token)
            if not mac_str:
                print(f"[sendfile] peer '{token}' not found. Use /peers.", flush=True)
                return True
            self.app.send_file(mac_str, path)
            return True

        if line.startswith("/senddir "):
            parts = line.split(" ", 2)
            if len(parts) != 3:
                print("[senddir] usage: /senddir <MAC|Name> </directory>", flush=True)
                return True
            token, dir_path = parts[1], parts[2]
            mac_str = self.app.resolve_mac(token)
            if not mac_str:
                print(f"[senddir] peer '{token}' not found. Use /peers.", flush=True)
                return True
            self.app.send_directory(mac_str, dir_path)
            return True

        return False

    # Helpers ------------------------------------------------------

    def print_help(self) -> None:
        print(
            """Commands:
  /me                       -> show your MAC
  /peers                    -> list peers (MAC, name, last_seen)
  /peers reset              -> clear peer table and file
  /peer <MAC|Name>          -> set active peer by MAC or Name
  /discover on|off          -> start or stop beacons
  /sendfile <MAC|Name> </path/to/file>   -> send file
    /senddir <MAC|Name> </path/to/dir>     -> send directory (replaces on receive)
  <free text>               -> send UNICAST to active peer
  /help                     -> this help
""",
            flush=True,
        )

    def _receive_only(self) -> None:
        print(
            "[info] No TTY; receive-only mode (discovery and file-transfer active).",
            flush=True,
        )
        while True:
            time.sleep(1)

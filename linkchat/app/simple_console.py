"""Simple console chat loop for running Link-Chat in terminals.

Designed for two Docker containers sharing the same Layer-2 segment. Launch the
script in each container, set the peer MAC address, and start exchanging
messages.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from typing import Iterable, Optional

from linkchat.backend import LinkChatBackend
from linkchat.constants import ETHERTYPE_DATA

PROMPT = "linkchat-simple> "


def _format_mac(mac: bytes) -> str:
    return ":".join(f"{b:02x}" for b in mac)


def _parse_mac(mac_str: str) -> bytes:
    parts = mac_str.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError("MAC must have 6 octets, e.g. aa:bb:cc:dd:ee:ff")
    try:
        return bytes(int(part, 16) for part in parts)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError("MAC contains non-hex digit") from exc


class SimpleConsole:
    def __init__(self, backend: LinkChatBackend, peer: Optional[bytes]) -> None:
        self.backend = backend
        self.peer = peer
        self.running = False

        backend.on_message_received = self._on_message

    def _on_message(self, src_mac: bytes, text: str) -> None:
        prefix = _format_mac(src_mac)
        print(f"\n[{prefix}] {text}")
        if self.running:
            print(PROMPT, end="", flush=True)

    def _print_help(self) -> None:
        print(
            "Commands:\n"
            "  /peer <mac>   set destination MAC (aa:bb:cc:dd:ee:ff)\n"
            "  /info         show local interface information\n"
            "  /quit         exit console\n"
            "Any other line is sent as a chat message."
        )

    def _show_info(self) -> None:
        info = self.backend.get_network_info()
        print(
            "interface={interface} mac={mac_address} medium={medium_type} "
            "running={running}".format(**info)
        )

    def _send(self, line: str) -> None:
        if self.peer is None:
            print("No peer configured. Use /peer <mac> first.")
            return
        try:
            delivered = self.backend.send_message(self.peer, line)
        except Exception as exc:  # pragma: no cover - surfaced to operator
            print(f"Send failed: {exc}")
            return
        if not delivered:
            print("Message not acknowledged.")

    def run(self) -> int:
        self.backend.start()
        info = self.backend.get_network_info()
        print(
            "Local interface {iface} MAC {mac}".format(
                iface=info["interface"],
                mac=info.get("mac_address") or "unknown",
            )
        )
        if self.peer is not None:
            print(f"Current peer: {_format_mac(self.peer)}")
        else:
            print("No peer set. Use /peer <mac> to configure a destination.")
        print("Type /help for commands.")

        self.running = True
        try:
            while True:
                try:
                    line = input(PROMPT)
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print()
                    break
                text = line.strip()
                if not text:
                    continue
                if text == "/help":
                    self._print_help()
                    continue
                if text == "/info":
                    self._show_info()
                    continue
                if text == "/quit":
                    break
                if text.startswith("/peer "):
                    mac_str = text[len("/peer ") :].strip()
                    try:
                        self.peer = _parse_mac(mac_str)
                    except ValueError as exc:
                        print(f"Invalid MAC: {exc}")
                        continue
                    print(f"Peer set to {_format_mac(self.peer)}")
                    continue
                self._send(text)
        finally:
            self.running = False
            self.backend.stop()
        return 0


def _parse_args(argv: Optional[Iterable[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple Link-Chat console")
    parser.add_argument(
        "--interface",
        "-i",
        help="Network interface to use (defaults to $LINKCHAT_INTERFACE or $INTERFACE)",
        default=None,
    )
    parser.add_argument(
        "--ethertype",
        type=lambda val: int(val, 0),
        default=ETHERTYPE_DATA,
        help="EtherType for Link-Chat frames (default: 0x%04x)" % ETHERTYPE_DATA,
    )
    parser.add_argument(
        "--peer",
        help="Destination MAC address (aa:bb:cc:dd:ee:ff)",
        default=None,
    )
    parser.add_argument(
        "--node-name",
        default=os.getenv("LINKCHAT_NODE"),
        help="Optional display name for peer discovery",
    )
    parser.add_argument(
        "--download-dir",
        default=os.getenv("LINKCHAT_DOWNLOAD_DIR", "./downloads"),
        help="Directory for incoming files",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LINKCHAT_LOG", "info"),
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging verbosity",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.interface is None:
        env_iface = os.getenv("LINKCHAT_INTERFACE") or os.getenv("INTERFACE")
        if env_iface:
            args.interface = env_iface
        else:
            parser.error("--interface not provided and LINKCHAT_INTERFACE is unset")
    return args


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    _configure_logging(args.log_level)

    peer_bytes: Optional[bytes] = None
    if args.peer:
        peer_bytes = _parse_mac(args.peer)

    backend = LinkChatBackend(
        interface=args.interface,
        ethertype=args.ethertype,
        download_dir=args.download_dir,
        node_name=args.node_name,
    )

    console = SimpleConsole(backend, peer_bytes)

    def _sigint_handler(_signo, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        return console.run()
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

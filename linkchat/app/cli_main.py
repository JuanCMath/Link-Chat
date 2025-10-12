"""Minimal console interface for exercising Link-Chat backend logic.

Run with ``python -m linkchat.app.cli_main --interface eth0`` or via the
``linkchat-cli`` console script entry point.
"""
from __future__ import annotations

import argparse
import logging
import os
import shlex
import signal
import sys
from typing import Iterable, Optional

from linkchat.backend import LinkChatBackend
from linkchat.constants import ETHERTYPE_DATA
from linkchat.link.peer_discovery import PeerInfo

PROMPT = "linkchat> "


def _format_mac(mac: bytes) -> str:
    return ":".join(f"{b:02x}" for b in mac)


def _parse_mac(value: str) -> bytes:
    parts = value.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError("MAC address must contain 6 octets (e.g., aa:bb:cc:dd:ee:ff)")
    try:
        return bytes(int(part, 16) for part in parts)
    except ValueError as exc:  # pragma: no cover - defensive parsing
        raise ValueError("Invalid hex digit in MAC address") from exc


class ConsoleApp:
    """Simple REPL that talks to the LinkChat backend."""

    def __init__(self, backend: LinkChatBackend) -> None:
        self.backend = backend
        self._running = False

        # Wire callbacks so inbound events are visible in the console.
        backend.on_message_received = self._on_message
        backend.on_peer_available = self._on_peer_available
        backend.on_peer_expired = self._on_peer_expired
        backend.on_file_progress = self._on_file_progress
        backend.on_file_complete = self._on_file_complete

    # -- callbacks -----------------------------------------------------
    def _emit(self, message: str, *, prompt: bool = True) -> None:
        print(f"\n{message}")
        if prompt and self._running:
            print(PROMPT, end="", flush=True)

    def _on_message(self, src_mac: bytes, text: str) -> None:
        self._emit(f"message from {_format_mac(src_mac)}: {text}")

    def _on_peer_available(self, peer: PeerInfo) -> None:
        label = peer.name or peer.node_id
        services = ",".join(sorted(peer.services)) or "-"
        self._emit(
            f"peer discovered {_format_mac(peer.mac)} name='{label}' services=[{services}]"
        )

    def _on_peer_expired(self, peer: PeerInfo) -> None:
        label = peer.name or peer.node_id
        self._emit(f"peer lost {_format_mac(peer.mac)} name='{label}'")

    def _on_file_progress(self, filename: str, bytes_done: int, total: int) -> None:
        self._emit(f"file progress {filename}: {bytes_done}/{total} bytes", prompt=False)

    def _on_file_complete(self, filename: str, success: bool) -> None:
        status = "done" if success else "failed"
        self._emit(f"file transfer {status}: {filename}")

    # -- command helpers ----------------------------------------------
    def _cmd_help(self) -> None:
        self._emit(
            "commands: help | info | peers | send <mac> <message> | "
            "sendfile <mac> <path> | quit",
            prompt=False,
        )

    def _cmd_info(self) -> None:
        info = self.backend.get_network_info()
        msg = (
            "interface={interface} mac={mac_address} medium={medium_type} "
            "running={running} ethertype={ethertype}"
        ).format(**info)
        self._emit(msg, prompt=False)

    def _cmd_peers(self) -> None:
        peers = self.backend.list_peers()
        if not peers:
            self._emit("no peers discovered", prompt=False)
            return
        for peer in peers:
            label = peer.name or peer.node_id
            services = ",".join(sorted(peer.services)) or "-"
            self._emit(
                f"peer {_format_mac(peer.mac)} name='{label}' services=[{services}]",
                prompt=False,
            )

    def _cmd_send(self, args: Iterable[str]) -> None:
        parts = list(args)
        if len(parts) < 2:
            self._emit("usage: send <mac> <message>")
            return
        mac_raw, message = parts[0], " ".join(parts[1:])
        try:
            dst = _parse_mac(mac_raw)
        except ValueError as exc:
            self._emit(f"invalid mac: {exc}")
            return
        try:
            success = self.backend.send_message(dst, message)
        except Exception as exc:  # pragma: no cover - surfaced for operator
            self._emit(f"send failed: {exc}")
            return
        if success:
            self._emit("message delivered", prompt=False)
        else:
            self._emit("message not acknowledged", prompt=False)

    def _cmd_sendfile(self, args: Iterable[str]) -> None:
        parts = list(args)
        if len(parts) != 2:
            self._emit("usage: sendfile <mac> <path>")
            return
        mac_raw, path = parts
        try:
            dst = _parse_mac(mac_raw)
        except ValueError as exc:
            self._emit(f"invalid mac: {exc}")
            return
        try:
            result = self.backend.send_file(dst, path)
        except Exception as exc:  # pragma: no cover - surfaced for operator
            self._emit(f"sendfile failed: {exc}")
            return
        if result:
            self._emit("file transfer complete", prompt=False)
        else:
            self._emit("file transfer failed", prompt=False)

    # -- lifecycle ----------------------------------------------------
    def run(self) -> int:
        self.backend.start()
        self.backend.add_service("chat")
        info = self.backend.get_network_info()
        print(
            "Link-Chat console ready on interface {iface} mac {mac}".format(
                iface=info["interface"],
                mac=info.get("mac_address") or "unknown",
            )
        )
        self._running = True
        try:
            while True:
                try:
                    raw = input(PROMPT)
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print()
                    break
                command = raw.strip()
                if not command:
                    continue
                tokens = shlex.split(command)
                op, *rest = tokens
                op = op.lower()
                if op in {"quit", "exit"}:
                    break
                if op == "help":
                    self._cmd_help()
                elif op == "info":
                    self._cmd_info()
                elif op == "peers":
                    self._cmd_peers()
                elif op == "send":
                    self._cmd_send(rest)
                elif op == "sendfile":
                    self._cmd_sendfile(rest)
                else:
                    self._emit(f"unknown command '{op}' - type 'help'")
        finally:
            self._running = False
            self.backend.stop()
        return 0


def _parse_args(argv: Optional[Iterable[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Link-Chat console interface")
    parser.add_argument(
        "--interface",
        "-i",
        default=None,
        help="Network interface to use (defaults to $LINKCHAT_INTERFACE or $INTERFACE)",
    )
    parser.add_argument(
        "--ethertype",
        type=lambda val: int(val, 0),
        default=ETHERTYPE_DATA,
        help="EtherType for Link-Chat data frames (default: 0x%04x)" % ETHERTYPE_DATA,
    )
    parser.add_argument(
        "--node-name",
        default=os.getenv("LINKCHAT_NODE", None),
        help="Optional display name advertised to peers",
    )
    parser.add_argument(
        "--download-dir",
        default=os.getenv("LINKCHAT_DOWNLOAD_DIR", "./downloads"),
        help="Directory for incoming files",
    )
    parser.add_argument(
        "--log",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.interface:
        env_iface = os.getenv("LINKCHAT_INTERFACE") or os.getenv("INTERFACE")
        if env_iface:
            args.interface = env_iface
        else:
            parser.error("--interface not provided and LINKCHAT_INTERFACE is unset")
    return args


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    _configure_logging(args.log)

    backend = LinkChatBackend(
        interface=args.interface,
        ethertype=args.ethertype,
        download_dir=args.download_dir,
        node_name=args.node_name,
    )

    app = ConsoleApp(backend)

    def _sigint_handler(_signo, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        return app.run()
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

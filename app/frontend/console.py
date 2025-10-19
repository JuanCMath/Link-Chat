"""
console.py
~~~~~~~~~~

Interactive console frontend for LinkChat application.

This module provides a command-line interface for interacting with the LinkChat
P2P messaging system. It handles user input, parses commands, and delegates
operations to the LinkChatApp backend.

Features:
    - Interactive command mode with REPL loop
    - Automatic fallback to receive-only mode for non-TTY environments
    - Peer management commands (/peers, /peer)
    - File and directory transfer commands (/sendfile, /senddir)
    - Discovery control (/discover on/off)
    - Free-text messaging to active peer

Architecture:
    The console acts as a thin presentation layer, forwarding all business
    logic to the LinkChatApp facade. This separation allows for easy
    implementation of alternative frontends (GUI, web, etc.).

Example:
    >>> from app.core.app_facade import LinkChatApp
    >>> from app.core.config import load_config
    >>> config = load_config()
    >>> app = LinkChatApp(config)
    >>> frontend = ConsoleFrontend(app)
    >>> frontend.run()  # Blocks until Ctrl+C
"""

import sys
import time
from typing import List

from ..backend.app_facade import LinkChatApp


class ConsoleFrontend:
    """
    Console-based user interface for LinkChat.

    This class provides an interactive command-line interface with two modes:
    1. Interactive mode (TTY available): Full command loop with user input
    2. Receive-only mode (no TTY): Passive listening for incoming messages

    The frontend handles command parsing and validation, delegating all
    network operations to the LinkChatApp backend.

    Attributes:
        app: LinkChatApp instance managing the backend services.

    Command Categories:
        - Status: /me, /peers
        - Configuration: /peer, /discover
        - Transfer: /sendfile, /senddir
        - Messaging: Free text (when active peer is set)

    Example:
        >>> app = LinkChatApp(config)
        >>> console = ConsoleFrontend(app)
        >>> console.run()
        Commands:
          /me                       -> show your MAC
          ...
        > Hello world!
    """

    def __init__(self, app: LinkChatApp) -> None:
        """
        Initialize console frontend with backend application.

        Args:
            app: Configured LinkChatApp instance ready to start.
        """
        self.app = app
        self.running = True

    def run(self) -> None:
        """
        Start the application and enter main loop.

        This method:
        1. Starts all backend services (sockets, discovery, transfers)
        2. Displays help message
        3. Enters interactive or receive-only mode based on TTY availability
        4. Ensures clean shutdown on exit (Ctrl+C or EOF)

        Blocks until interrupted (KeyboardInterrupt) or STDIN closes.

        Example:
            >>> frontend = ConsoleFrontend(app)
            >>> try:
            ...     frontend.run()
            ... except KeyboardInterrupt:
            ...     print("Shutting down...")

        Note:
            In Docker containers without TTY, automatically enters receive-only mode.
        """
        self.app.start()
        self.print_help()

        try:
            if sys.stdin.isatty():
                self._interactive_loop()
            else:
                self._receive_only()
        finally:
            self.app.stop()

    # Command Loop ----------------------------------------------------------

    def _interactive_loop(self) -> None:
        """
        Main interactive command loop (REPL).

        Continuously prompts for user input, handling commands and free-text
        messages. Commands start with '/' and are processed by _handle_command().
        Other input is sent as chat message to the active peer.

        Terminates on EOF (Ctrl+D), transitioning to receive-only mode to
        keep the application running for incoming messages.

        Flow:
            1. Display prompt (">")
            2. Read user input
            3. If command (/xxx), process it
            4. Otherwise, send as chat message
            5. Repeat until EOF or KeyboardInterrupt

        Note:
            Empty lines are ignored (no-op).
        """
        while self.running:
            try:
                line = input("> ").strip()
            except EOFError:
                # User pressed Ctrl+D or STDIN closed
                print("[info] STDIN closed; switching to receive-only mode.", flush=True)
                self._receive_only()
                return

            if not line:
                continue  # Ignore empty input

            if line == "/help":
                self.print_help()
                continue

            # Try to handle as command; if not a command, send as chat
            if self._handle_command(line):
                continue

            # Free text message (requires active peer)
            self.app.send_chat(line)

    def _handle_command(self, line: str) -> bool:
        """
        Parse and execute a console command.

        Commands are slash-prefixed (/command) and provide various application
        functions like peer management, file transfer, and configuration.

        Args:
            line: User input line (already stripped of whitespace).

        Returns:
            bool: True if line was recognized as a command (even if invalid args),
                  False if line is not a command and should be treated as chat message.

        Supported Commands:
            /me                             - Display local MAC and name
            /peers                          - List all discovered peers
            /peers reset                    - Clear peer database
            /peer <MAC|Name>                - Set active peer for chat
            /discover on|off                - Control beacon broadcasts
            /sendfile <MAC|Name> <path>     - Transfer file to peer
            /senddir <MAC|Name> <path>      - Transfer directory to peer
            /sendtoall <text>               - Send message to everyone in the network
            /ifaces                         - Show available interfaces 
            /config show                    - Display current configuration
            /config set <param> <value>     - Set configuration parameter
            /quit                           - Shut down the program

        Example:
            >>> frontend._handle_command("/peers")
            True  # Command was handled
            >>> frontend._handle_command("Hello")
            False  # Not a command
        """
        # Command: /me - Show local MAC address
        if line == "/me":
            mac = self.app.get_mac_address()
            if mac:
                print(f"[me] {mac} ({self.app.config.name})", flush=True)
            return True

        # Command: /peers - List discovered peers
        if line == "/peers":
            peers = self.app.list_peers()
            if not peers:
                print("[peers] No peers discovered yet.", flush=True)
            else:
                for peer in peers:
                    name_display = peer.name or "(unknown)"
                    print(
                        f"  {peer.mac}\t{name_display}\t{peer.last_seen}",
                        flush=True,
                    )
            return True

        # Command: /peers reset - Clear peer database
        if line == "/peers reset":
            self.app.reset_peers()
            print("[peers] Peer table and file cleared.", flush=True)
            return True

        # Command: /peer <token> - Set active peer
        if line.startswith("/peer "):
            token = line.split(" ", 1)[1].strip()
            mac_address = self.app.resolve_mac(token)
            if not mac_address:
                print(
                    f"[peer] Peer '{token}' not found. Use /peers to list available peers.",
                    flush=True,
                )
                return True
            if self.app.set_active_peer(mac_address):
                print(f"[peer] Active destination set to {mac_address}", flush=True)
            return True

        # Command: /discover on|off - Control beacon broadcasts
        if line.startswith("/discover "):
            arg = line.split(" ", 1)[1].strip().lower()
            if arg == "off":
                self.app.set_discovery(False)
            elif arg == "on":
                self.app.set_discovery(True)
            else:
                print("[discover] Usage: /discover on | /discover off", flush=True)
            return True

        # Command: /sendfile <token> <path> - Transfer file
        if line.startswith("/sendfile "):
            parts = line.split(" ", 2)
            if len(parts) != 3:
                print(
                    "[sendfile] Usage: /sendfile <MAC|Name> </local/path>",
                    flush=True,
                )
                return True

            token, file_path = parts[1], parts[2]
            mac_address = self.app.resolve_mac(token)
            if not mac_address:
                print(
                    f"[sendfile] Peer '{token}' not found. Use /peers to list available peers.",
                    flush=True,
                )
                return True

            self.app.send_file(mac_address, file_path)
            return True

        # Command: /senddir <token> <path> - Transfer directory
        if line.startswith("/senddir "):
            parts = line.split(" ", 2)
            if len(parts) != 3:
                print(
                    "[senddir] Usage: /senddir <MAC|Name> </directory>",
                    flush=True,
                )
                return True

            token, directory_path = parts[1], parts[2]
            mac_address = self.app.resolve_mac(token)
            if not mac_address:
                print(
                    f"[senddir] Peer '{token}' not found. Use /peers to list available peers.",
                    flush=True,
                )
                return True

            self.app.send_directory(mac_address, directory_path)
            return True

        # Command: /sendtoall <text> - Send broadcast
        if line.startswith("/sendtoall"):
            parts = line.split(" ", 1)
            if len(parts) != 2:
                print(
                    "[sendtoall] Usage: /sendtoall <text>",
                    flush=True,
                )
                return True
            
            self.app.broadcast_chat(parts[1])
            return True
        
        # Command: /ifaces - Show available interfaces
        if line.startswith("/ifaces"):
            parts = line.split(" ", 1)
            if len(parts) > 1:
                print(
                    "[ifaces] Usage: /ifaces",
                    flush=True,
                )
            
            else:
                from ..backend.utils.network_utils import list_network_interfaces
                ifaces = list_network_interfaces()
                ConsoleFrontend.show_ifaces(ifaces)
                    
            return True


        # Command family: /config
        if line.startswith("/config"):
            parts = line.split(" ", 3)

            # Command: /config show - Display current configuration
            if len(parts) == 2 and parts[1] == "show":
                config_params = self.app.show_config()
                for param in config_params:
                    print(param, flush=True)
                return True
            
            # Command: /config set <param> <value> - Set configuration parameter
            elif len(parts) == 4 and parts[1] == "set":
                param, value = parts[2], parts[3]
                print(self.app.set_config_param(param, value), flush = True)
                return True  

            else:
                print("[config] Usage: 1) /config set <param> <value> | 2) /config show", flush=True)
                return True         


        # Command: /quit - Shut down program
        if line.startswith("/quit"):
            parts = line.split(" ", 1)
            if len(parts) > 1:
                print(
                    "[quit] Usage: /quit",
                    flush=True,
                )
                return True
            
            self.running = False
            self.app.stop()
            return True
        

        # Not a recognized command
        return False

    # Helper Methods --------------------------------------------------------

    def print_help(self) -> None:
        """
        Display help message with available commands.

        Prints a formatted list of all console commands with brief descriptions
        and usage examples. Called automatically on startup and when user
        types /help.

        Example:
            >>> frontend.print_help()
            Commands:
              /me                       -> show your MAC
              ...
        """
        print(
            """Commands:
                /me                                     -> Show your MAC address and name
                /peers                                  -> List all discovered peers
                /peers reset                            -> Clear peer table and persistence file
                /peer <MAC|Name>                        -> Set active peer for chat messages
                /discover on|off                        -> Start or stop beacon broadcasts
                /sendfile <MAC|Name> </path/to/file>    -> Send file to peer
                /senddir <MAC|Name> </path/to/dir>      -> Send directory (tar.gz, replaces on receive)
                /sendtoall <text>                       -> Send chat message to everyone in the network
                /ifaces                                 -> Show available interfaces
                /config show                            -> Display current configuration
                /config set <param> <value>             -> Set configuration parameter
                <free text>                             -> Send chat message to active peer
                /help                                   -> Show this help message
                /quit                                   -> Shut down the program
            """,
            flush=True,
        )

    def _receive_only(self) -> None:
        """
        Enter passive receive-only mode.

        Used when no TTY is available (e.g., Docker containers, piped input).
        Keeps the application running to receive incoming messages, beacons,
        and file transfers, but doesn't accept user commands.

        Infinite loop that sleeps to prevent busy-waiting. The application
        continues to process network events in background threads.

        Example:
            >>> # In Docker without -it flags:
            >>> frontend.run()  # Automatically calls _receive_only()
            [info] No TTY; receive-only mode (discovery and file-transfer active).
        """
        print(
            "[info] No TTY detected; entering receive-only mode.",
            flush=True,
        )
        print(
            "[info] Discovery and file-transfer services remain active.",
            flush=True,
        )

        # Infinite sleep loop to keep application alive
        while True:
            time.sleep(1)

    @staticmethod
    def show_ifaces(ifaces: List[str]) -> None:
        """Prints available interfaces

        Args:
            ifaces (List[str]): list of formated strings "<param>: <values>"
        """
        print("Available interfaces:", flush=True)
        for index, iface in enumerate(ifaces):
            print(f"[{index}] {iface}", flush=True)
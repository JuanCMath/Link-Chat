"""
main.py
~~~~~~~

Entry point for the LinkChat peer-to-peer messaging application.

This module provides the primary executable entry point for LinkChat. It
initializes the application with environment-based configuration, starts
all networking services, and launches the interactive console interface.

Usage:
    Run directly from command line:
        $ python main.py

    Or as a module:
        $ python -m main

    In Docker:
        $ docker-compose up

Environment Variables:
    All configuration is loaded via environment variables. See app.core.config
    for the complete list of available options. Key variables include:

    - IFACE: Network interface name (default: eth0)
    - NAME: Local peer name for identification
    - ETHERTYPE: Custom EtherType value (default: 0x88B5)
    - PEERS_FILE: Path to peer persistence file
    - INBOX_DIR: Directory for received files

Execution Flow:
    1. Load configuration from environment variables
    2. Initialize LinkChatApp with configuration
    3. Create ConsoleFrontend with app instance
    4. Run interactive loop until Ctrl+C
    5. Clean shutdown of all services

Example:
    >>> # Set environment variables
    >>> import os
    >>> os.environ['NAME'] = 'Alice'
    >>> os.environ['IFACE'] = 'eth0'
    >>> 
    >>> # Run application
    >>> from main import main
    >>> main()
    [up] iface=eth0 mac=aa:bb:cc:dd:ee:ff name=Alice
    >

Note:
    The application requires raw socket privileges (CAP_NET_RAW on Linux or
    root/administrator access). Docker deployments handle this automatically.
"""
from app.core.app_facade import LinkChatApp
from app.core.config import load_config
from app.frontend.console import ConsoleFrontend


def main() -> None:
    """
    Main entry point for LinkChat application.

    Initializes the application with environment-based configuration,
    starts the console frontend, and handles graceful shutdown on
    keyboard interrupt (Ctrl+C).

    The function performs the following steps:
    1. Load configuration from environment variables
    2. Create LinkChatApp instance with loaded config
    3. Create ConsoleFrontend and start interactive loop
    4. Handle KeyboardInterrupt for clean exit

    Raises:
        SystemExit: Implicitly on unhandled exceptions
        KeyboardInterrupt: Caught and suppressed for clean shutdown

    Example:
        >>> if __name__ == "__main__":
        ...     main()
        [init] peers loaded: 3
        [up] iface=eth0 mac=aa:bb:cc:dd:ee:ff name=Alice
        > /peers
          aa:bb:cc:dd:ee:ff    Bob    2025-10-13T10:30:00Z
        > Hello world!
        [tx → aa:bb:cc:dd:ee:ff] Hello world!
        ^C
        # Clean shutdown
    """
    config = load_config()
    app = LinkChatApp(config)
    try:
        ConsoleFrontend(app).run()
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        pass


if __name__ == "__main__":
    main()

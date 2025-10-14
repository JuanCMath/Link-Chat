"""
Frontend Interface Implementations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

User interface modules for LinkChat application.

This package contains frontend implementations that interact with the
backend application facade. Currently supports console-based interaction,
with extensibility for future GUI or web interfaces.

Modules:
    console: Interactive command-line interface (REPL)

Architecture:
    Frontends act as thin presentation layers, delegating all business
    logic to the LinkChatApp facade. This separation enables multiple
    frontend implementations to share the same backend.

Example:
    >>> from app.backend.app_facade import LinkChatApp
    >>> from app.backend.core.config import load_config
    >>> from app.frontend.console import ConsoleFrontend
    >>> 
    >>> config = load_config()
    >>> app = LinkChatApp(config)
    >>> console = ConsoleFrontend(app)
    >>> console.run()  # Start interactive session
"""

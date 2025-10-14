from app.core.app_facade import LinkChatApp
from app.core.config import load_config
from app.frontend.console import ConsoleFrontend


def main() -> None:
    config = load_config()
    app = LinkChatApp(config)
    try:
        ConsoleFrontend(app).run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

"""Main entry point for audiobook generator."""
from src.config import Config
from src.app import run_audiobook_generator


def main():
    """Main entry point - parse config and run application."""
    config = Config.from_cli()
    config.validate()
    run_audiobook_generator(config)


if __name__ == "__main__":
    main()

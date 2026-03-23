import argparse

from .__meta__ import __version__


def main() -> None:
    """CLI entry-point."""
    parser = argparse.ArgumentParser(
        prog="ton-connect",
        description="TON Connect CLI.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"ton-connect {__version__}",
    )
    parser.parse_args()


if __name__ == "__main__":
    main()

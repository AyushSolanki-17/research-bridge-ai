"""Command-line entrypoint, independent of server dependencies."""

import argparse

from research_bridge import __version__


def main() -> None:
    parser = argparse.ArgumentParser(description="Research Bridge command-line tools")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()
    parser.print_help()

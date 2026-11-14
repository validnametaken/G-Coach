"""Command-line launcher for the G-Coach desktop application."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gcoach",
        description="Launch G-Coach, the local desktop writing assistant.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        type=str.upper,
        help="set console logging verbosity (default: INFO)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse launcher options and run the desktop application."""
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        # Import after parsing so --help works without loading PyQt6 or Windows APIs.
        from core.ui.window import main as run_desktop_app

        return run_desktop_app()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("G-Coach interrupted by user.")
        return 130
    except Exception:
        logging.getLogger(__name__).exception("G-Coach failed to start.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

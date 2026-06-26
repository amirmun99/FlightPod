"""Entry point: ``python -m flightpaper.main`` (or the ``flightpaper`` console script)."""

from __future__ import annotations

import argparse
import logging
import os

import uvicorn

from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(description="FlightPaper Pi service")
    parser.add_argument(
        "--host",
        default=os.environ.get("FLIGHTPAPER_HOST", "0.0.0.0"),
        help="ASGI bind host (default 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FLIGHTPAPER_PORT", "8080")),
        help="ASGI bind port (default 8080).",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("FLIGHTPAPER_LOG_LEVEL", "info"),
        help="uvicorn log level.",
    )
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return

    logging.getLogger("uvicorn.access").propagate = False
    uvicorn.run(
        "flightpaper.api.server:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=False,
    )


if __name__ == "__main__":
    main()

"""Command line entry point: python3 -m taglog_web [options]."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def main(argv=None) -> int:
    if sys.version_info < (3, 8):
        print("taglog-web needs Python 3.8 or newer.", file=sys.stderr)
        return 1
    p = argparse.ArgumentParser(prog="taglog-web",
                                description="Browser-based taglog time logger and diary.")
    p.add_argument("-c", "--prefs", help="preferences file to use (default ~/.taglog)")
    p.add_argument("-p", "--port", type=int, default=8765, help="port to listen on (default 8765)")
    p.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    p.add_argument("--version", action="version", version=f"taglog-web {__version__}")
    args = p.parse_args(argv)

    from .server import serve
    try:
        serve(args.port, args.prefs, not args.no_browser)
    except OSError as e:
        if getattr(e, "errno", None) in (48, 98):  # address in use (macOS, Linux)
            print(f"Port {args.port} is already in use - is taglog-web already running?\n"
                  f"Open http://127.0.0.1:{args.port}/ or start with --port <other>.",
                  file=sys.stderr)
            return 1
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())

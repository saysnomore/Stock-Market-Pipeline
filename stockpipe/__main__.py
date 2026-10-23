import argparse
import logging
from pathlib import Path

from . import config
from .export import export_all
from .pipeline import run


def build_parser():
    parser = argparse.ArgumentParser(prog="stockpipe")
    parser.add_argument("--db", type=Path, default=config.DB_PATH)
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--tickers", nargs="+", default=list(config.SYMBOLS))
    run_parser.add_argument("--start", default=config.DEFAULT_START)
    run_parser.add_argument("--full-refresh", action="store_true")
    run_parser.add_argument("--export", action="store_true")
    run_parser.add_argument("--out", type=Path, default=config.EXPORT_DIR)

    export_parser = sub.add_parser("export")
    export_parser.add_argument("--out", type=Path, default=config.EXPORT_DIR)

    return parser


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_parser().parse_args()

    if args.command == "run":
        run(args.tickers, args.db, args.start, full_refresh=args.full_refresh)
        if args.export:
            export_all(args.db, args.out)
    elif args.command == "export":
        export_all(args.db, args.out)


if __name__ == "__main__":
    main()

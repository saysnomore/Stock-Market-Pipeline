import logging
from datetime import date, timedelta

from . import config
from .db import connect, init_schema
from .extract import fetch_prices
from .load import finish_run, latest_dates, start_run, upsert_prices, upsert_symbols
from .transform import clean_prices

log = logging.getLogger(__name__)


def build_metadata(symbols):
    metadata = {}
    for symbol in symbols:
        info = config.SYMBOLS.get(symbol)
        if info is None:
            info = {"name": symbol, **config.UNKNOWN_SYMBOL}
        metadata[symbol] = info
    return metadata


def resolve_start(latest, full_refresh, default_start, overlap_days=config.OVERLAP_DAYS):
    if full_refresh or latest is None:
        return default_start
    return (date.fromisoformat(latest) - timedelta(days=overlap_days)).isoformat()


def run(symbols, db_path, start, full_refresh=False, fetcher=fetch_prices):
    symbols = [symbol.strip().upper() for symbol in symbols]
    total_rows = 0
    failed = []

    with connect(db_path) as conn:
        init_schema(conn)
        upsert_symbols(conn, build_metadata(symbols))
        run_id = start_run(conn)
        conn.commit()

        try:
            latest = latest_dates(conn)
            for symbol in symbols:
                symbol_start = resolve_start(latest.get(symbol), full_refresh, start)
                try:
                    raw = fetcher(symbol, symbol_start)
                    clean = clean_prices(raw)
                except Exception:
                    log.exception("failed to process %s", symbol)
                    failed.append(symbol)
                    continue
                if clean.empty:
                    log.info("%s: no rows to load", symbol)
                    continue
                loaded = upsert_prices(conn, clean)
                total_rows += loaded
                log.info("%s: upserted %d rows from %s", symbol, loaded, symbol_start)

            if failed and len(failed) == len(symbols):
                status = "failed"
            elif failed:
                status = "partial"
            else:
                status = "success"
            message = f"failed symbols: {', '.join(failed)}" if failed else None
            finish_run(conn, run_id, status, total_rows, message)
        except Exception as exc:
            conn.rollback()
            finish_run(conn, run_id, "failed", 0, str(exc))
            conn.commit()
            raise

    log.info("run finished: %d rows, %d failed symbols", total_rows, len(failed))
    return total_rows

from datetime import datetime, timezone

UPSERT_SYMBOL = """
INSERT INTO symbols (symbol, name, asset_type, sector)
VALUES (?, ?, ?, ?)
ON CONFLICT (symbol) DO UPDATE SET
    name = excluded.name,
    asset_type = excluded.asset_type,
    sector = excluded.sector
"""

UPSERT_PRICE = """
INSERT INTO daily_prices (symbol, trade_date, open, high, low, close, adj_close, volume)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (symbol, trade_date) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    adj_close = excluded.adj_close,
    volume = excluded.volume,
    loaded_at = CURRENT_TIMESTAMP
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_symbols(conn, metadata):
    rows = [
        (symbol, info["name"], info["asset_type"], info["sector"])
        for symbol, info in metadata.items()
    ]
    conn.executemany(UPSERT_SYMBOL, rows)


def upsert_prices(conn, frame):
    rows = [
        (
            row.symbol,
            row.trade_date,
            float(row.open),
            float(row.high),
            float(row.low),
            float(row.close),
            float(row.adj_close),
            int(row.volume),
        )
        for row in frame.itertuples(index=False)
    ]
    conn.executemany(UPSERT_PRICE, rows)
    return len(rows)


def latest_dates(conn):
    cursor = conn.execute("SELECT symbol, MAX(trade_date) FROM daily_prices GROUP BY symbol")
    return dict(cursor.fetchall())


def start_run(conn):
    cursor = conn.execute(
        "INSERT INTO pipeline_runs (started_at, status) VALUES (?, 'running')",
        (_now(),),
    )
    return cursor.lastrowid


def finish_run(conn, run_id, status, rows_loaded, message):
    conn.execute(
        "UPDATE pipeline_runs SET finished_at = ?, status = ?, rows_loaded = ?, message = ? WHERE run_id = ?",
        (_now(), status, rows_loaded, message, run_id),
    )

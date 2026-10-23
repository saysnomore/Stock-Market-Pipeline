import logging

import pandas as pd

from .db import connect, init_schema

log = logging.getLogger(__name__)

EXPORT_QUERIES = {
    "price_metrics": "SELECT * FROM v_price_metrics ORDER BY symbol, trade_date",
    "monthly_summary": "SELECT * FROM v_monthly_summary ORDER BY symbol, year_month",
    "latest_snapshot": "SELECT * FROM v_latest_snapshot ORDER BY symbol",
}


def export_all(db_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with connect(db_path) as conn:
        init_schema(conn)
        for name, query in EXPORT_QUERIES.items():
            frame = pd.read_sql_query(query, conn).round(6)
            path = out_dir / f"{name}.csv"
            frame.to_csv(path, index=False)
            log.info("wrote %s (%d rows)", path, len(frame))
            paths.append(path)
    return paths

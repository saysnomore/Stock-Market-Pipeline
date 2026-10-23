import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def fetch_prices(symbol, start, end=None):
    frame = yf.Ticker(symbol).history(
        start=start,
        end=end,
        auto_adjust=False,
        actions=False,
    )
    if frame is None or frame.empty:
        log.warning("no data returned for %s", symbol)
        return pd.DataFrame()
    frame = frame.reset_index()
    frame = frame.rename(columns={frame.columns[0]: "trade_date"})
    frame["symbol"] = symbol
    return frame

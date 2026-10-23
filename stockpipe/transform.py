import pandas as pd

OUTPUT_COLUMNS = ["symbol", "trade_date", "open", "high", "low", "close", "adj_close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close"]
RENAMES = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def clean_prices(raw):
    if raw is None or raw.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    frame = raw.rename(columns=RENAMES)
    missing = [column for column in OUTPUT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    frame = frame[OUTPUT_COLUMNS].copy()

    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()

    dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    frame["trade_date"] = dates.dt.strftime("%Y-%m-%d")

    for column in PRICE_COLUMNS + ["volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["trade_date"] + PRICE_COLUMNS)
    frame = frame[(frame[PRICE_COLUMNS] > 0).all(axis=1)]
    frame = frame[frame["high"] >= frame["low"]]

    frame["volume"] = frame["volume"].fillna(0).clip(lower=0).astype("int64")
    frame[PRICE_COLUMNS] = frame[PRICE_COLUMNS].round(4)

    frame = frame.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
    return frame.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

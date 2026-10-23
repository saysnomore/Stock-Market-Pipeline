import pandas as pd
import pytest

from stockpipe.transform import OUTPUT_COLUMNS, clean_prices

RAW_COLUMNS = ["trade_date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "symbol"]


def make_raw(rows):
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


def test_empty_input_returns_empty_frame_with_schema():
    result = clean_prices(pd.DataFrame())
    assert result.empty
    assert list(result.columns) == OUTPUT_COLUMNS


def test_renames_and_orders_columns():
    raw = make_raw([["2024-01-02", 10, 12, 9, 11, 10.5, 1000, "aapl"]])
    result = clean_prices(raw)
    assert list(result.columns) == OUTPUT_COLUMNS
    assert result.loc[0, "symbol"] == "AAPL"
    assert result.loc[0, "adj_close"] == 10.5


def test_strips_timezone_and_keeps_local_date():
    dates = pd.date_range("2024-01-02", periods=2, tz="America/New_York")
    raw = make_raw([[d, 10, 12, 9, 11, 10.5, 1000, "SPY"] for d in dates])
    result = clean_prices(raw)
    assert result["trade_date"].tolist() == ["2024-01-02", "2024-01-03"]


def test_drops_duplicates_keeping_last():
    raw = make_raw(
        [
            ["2024-01-02", 10, 12, 9, 11, 10.5, 1000, "SPY"],
            ["2024-01-02", 10, 13, 9, 12, 11.5, 2000, "SPY"],
        ]
    )
    result = clean_prices(raw)
    assert len(result) == 1
    assert result.loc[0, "close"] == 12


def test_drops_rows_with_missing_or_non_positive_prices():
    raw = make_raw(
        [
            ["2024-01-02", 10, 12, 9, None, 10.5, 1000, "SPY"],
            ["2024-01-03", 10, 12, 9, 0, 10.5, 1000, "SPY"],
            ["2024-01-04", 10, 12, 9, 11, -1, 1000, "SPY"],
            ["2024-01-05", 10, 12, 9, 11, 10.5, 1000, "SPY"],
        ]
    )
    result = clean_prices(raw)
    assert result["trade_date"].tolist() == ["2024-01-05"]


def test_drops_rows_where_high_is_below_low():
    raw = make_raw(
        [
            ["2024-01-02", 10, 8, 9, 9, 9, 1000, "SPY"],
            ["2024-01-03", 10, 12, 9, 11, 10.5, 1000, "SPY"],
        ]
    )
    result = clean_prices(raw)
    assert result["trade_date"].tolist() == ["2024-01-03"]


def test_missing_volume_becomes_zero_integer():
    raw = make_raw([["2024-01-02", 10, 12, 9, 11, 10.5, None, "SPY"]])
    result = clean_prices(raw)
    assert result.loc[0, "volume"] == 0
    assert str(result["volume"].dtype) == "int64"


def test_sorted_by_symbol_then_date():
    raw = make_raw(
        [
            ["2024-01-03", 10, 12, 9, 11, 10.5, 1, "SPY"],
            ["2024-01-02", 10, 12, 9, 11, 10.5, 1, "SPY"],
            ["2024-01-02", 10, 12, 9, 11, 10.5, 1, "AAPL"],
        ]
    )
    result = clean_prices(raw)
    assert list(zip(result["symbol"], result["trade_date"])) == [
        ("AAPL", "2024-01-02"),
        ("SPY", "2024-01-02"),
        ("SPY", "2024-01-03"),
    ]


def test_missing_required_columns_raises():
    raw = pd.DataFrame({"trade_date": ["2024-01-02"], "symbol": ["SPY"], "Open": [1]})
    with pytest.raises(ValueError):
        clean_prices(raw)

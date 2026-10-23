import pandas as pd
import pytest

from stockpipe.db import connect, init_schema
from stockpipe.load import upsert_prices, upsert_symbols

META = {"TEST": {"name": "Test Corp", "asset_type": "Equity", "sector": "Testing"}}


def build_prices(periods=250):
    dates = pd.bdate_range("2023-01-02", periods=periods)
    values = [100.0 + i for i in range(periods)]
    return pd.DataFrame(
        {
            "symbol": "TEST",
            "trade_date": dates.strftime("%Y-%m-%d"),
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "adj_close": values,
            "volume": 1000,
        }
    )


@pytest.fixture
def conn(tmp_path):
    with connect(tmp_path / "test.db") as connection:
        init_schema(connection)
        upsert_symbols(connection, META)
        upsert_prices(connection, build_prices())
        yield connection


def fetch_metrics(conn):
    return conn.execute(
        "SELECT trade_date, adj_close, daily_return, sma_20, sma_50, sma_200, "
        "volatility_20d, drawdown, trend_signal FROM v_price_metrics "
        "WHERE symbol = 'TEST' ORDER BY trade_date"
    ).fetchall()


def test_moving_averages_require_full_window(conn):
    rows = fetch_metrics(conn)
    assert rows[18][3] is None
    assert rows[19][3] == pytest.approx(sum(100 + i for i in range(20)) / 20)
    assert rows[48][4] is None
    assert rows[49][4] == pytest.approx(sum(100 + i for i in range(50)) / 50)
    assert rows[198][5] is None
    assert rows[199][5] == pytest.approx(sum(100 + i for i in range(200)) / 200)


def test_daily_return_and_volatility(conn):
    rows = fetch_metrics(conn)
    assert rows[0][2] is None
    assert rows[1][2] == pytest.approx(101 / 100 - 1)
    assert rows[19][6] is None
    assert rows[20][6] is not None
    assert rows[20][6] > 0


def test_drawdown_is_zero_in_monotonic_uptrend(conn):
    rows = fetch_metrics(conn)
    assert all(row[7] == pytest.approx(0.0) for row in rows)


def test_trend_signal_is_bullish_when_short_average_above_long(conn):
    rows = fetch_metrics(conn)
    assert rows[198][8] is None
    assert rows[199][8] == "Bullish"


def test_drawdown_after_decline(tmp_path):
    prices = build_prices(30)
    prices.loc[29, ["open", "high", "low", "close", "adj_close"]] = 100.0 + 20
    with connect(tmp_path / "dd.db") as connection:
        init_schema(connection)
        upsert_symbols(connection, META)
        upsert_prices(connection, prices)
        last = connection.execute(
            "SELECT drawdown FROM v_price_metrics ORDER BY trade_date DESC LIMIT 1"
        ).fetchone()[0]
    assert last == pytest.approx(120.0 / 128.0 - 1)


def test_monthly_summary(conn):
    rows = conn.execute(
        "SELECT year_month, monthly_return, trading_days FROM v_monthly_summary "
        "WHERE symbol = 'TEST' ORDER BY year_month"
    ).fetchall()
    assert rows[0][0] == "2023-01"
    assert rows[0][1] is None
    assert all(row[1] is not None and row[1] > 0 for row in rows[1:])
    assert sum(row[2] for row in rows) == 250


def test_latest_snapshot_returns_one_row_per_symbol(conn):
    rows = conn.execute("SELECT symbol, adj_close, high_52w, low_52w FROM v_latest_snapshot").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "TEST"
    assert rows[0][1] == pytest.approx(100.0 + 249)
    assert rows[0][2] == pytest.approx(100.0 + 249)
    assert rows[0][3] < rows[0][2]

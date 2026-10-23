import pandas as pd

from stockpipe.db import connect
from stockpipe.export import export_all
from stockpipe.pipeline import resolve_start, run


def fake_fetcher(symbol, start, end=None):
    dates = pd.bdate_range("2024-01-02", periods=30, tz="America/New_York")
    values = [50.0 + i for i in range(30)]
    return pd.DataFrame(
        {
            "trade_date": dates,
            "Open": values,
            "High": [v + 1 for v in values],
            "Low": [v - 1 for v in values],
            "Close": values,
            "Adj Close": values,
            "Volume": [1000 + i for i in range(30)],
            "symbol": symbol,
        }
    )


def flaky_fetcher(symbol, start, end=None):
    if symbol == "JPM":
        raise RuntimeError("network down")
    return fake_fetcher(symbol, start, end)


def count(db_path, query):
    with connect(db_path) as conn:
        return conn.execute(query).fetchone()[0]


def test_resolve_start():
    assert resolve_start(None, False, "2015-01-01") == "2015-01-01"
    assert resolve_start("2024-03-15", True, "2015-01-01") == "2015-01-01"
    assert resolve_start("2024-03-15", False, "2015-01-01", 7) == "2024-03-08"


def test_run_is_idempotent(tmp_path):
    db = tmp_path / "p.db"
    assert run(["AAPL", "JPM"], db, "2024-01-01", fetcher=fake_fetcher) == 60
    assert run(["AAPL", "JPM"], db, "2024-01-01", fetcher=fake_fetcher) == 60
    assert count(db, "SELECT COUNT(*) FROM daily_prices") == 60
    assert count(db, "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'success'") == 2


def test_partial_failure_is_recorded(tmp_path):
    db = tmp_path / "p.db"
    assert run(["AAPL", "JPM"], db, "2024-01-01", fetcher=flaky_fetcher) == 30
    assert count(db, "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'partial'") == 1
    assert count(db, "SELECT COUNT(*) FROM daily_prices WHERE symbol = 'AAPL'") == 30
    assert count(db, "SELECT COUNT(*) FROM daily_prices WHERE symbol = 'JPM'") == 0


def test_export_writes_expected_files(tmp_path):
    db = tmp_path / "p.db"
    run(["AAPL"], db, "2024-01-01", fetcher=fake_fetcher)
    paths = export_all(db, tmp_path / "out")
    assert sorted(path.name for path in paths) == [
        "latest_snapshot.csv",
        "monthly_summary.csv",
        "price_metrics.csv",
    ]
    metrics = pd.read_csv(tmp_path / "out" / "price_metrics.csv")
    assert len(metrics) == 30
    assert "sma_20" in metrics.columns

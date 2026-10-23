from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "market.db"
EXPORT_DIR = BASE_DIR / "exports"
SQL_DIR = BASE_DIR / "sql"

DEFAULT_START = "2015-01-01"
OVERLAP_DAYS = 7

SYMBOLS = {
    "SPY": {"name": "SPDR S&P 500 ETF Trust", "asset_type": "ETF", "sector": "Broad Market"},
    "AAPL": {"name": "Apple Inc.", "asset_type": "Equity", "sector": "Technology"},
    "JPM": {"name": "JPMorgan Chase & Co.", "asset_type": "Equity", "sector": "Financials"},
    "XOM": {"name": "Exxon Mobil Corporation", "asset_type": "Equity", "sector": "Energy"},
    "JNJ": {"name": "Johnson & Johnson", "asset_type": "Equity", "sector": "Health Care"},
}

UNKNOWN_SYMBOL = {"asset_type": "Unknown", "sector": "Unknown"}

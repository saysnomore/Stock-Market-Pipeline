# Stock Market Data Pipeline + Dashboard

An end-to-end data engineering project: pull daily prices with `yfinance`, clean and validate them in pandas, store them in SQLite with a proper schema, compute trend analytics in SQL (moving averages, returns, volatility, drawdown, crossover signals), and explore everything in an interactive Streamlit dashboard (or export CSVs for Tableau).

**Stack:** Python, SQL (SQLite), pandas, yfinance, Streamlit, Plotly (optional: Tableau)
**Domains:** Data Engineering, Data Science, Capital Markets

Default universe: `SPY` (S&P 500 ETF), `AAPL` (Technology), `JPM` (Financials), `XOM` (Energy), `JNJ` (Health Care).

---

## Architecture

```
 yfinance ──► extract ──► transform ──► load ──► SQLite ──► SQL views ──► CSV export ──► Tableau
 (Yahoo)     raw OHLCV    clean +        upsert    market.db   v_price_metrics   exports/*.csv   dashboard
                          validate       (idempotent)           v_monthly_summary
                                                                v_latest_snapshot
```

| Stage | Module | Responsibility |
|---|---|---|
| Extract | `stockpipe/extract.py` | Download unadjusted OHLCV plus Adj Close per ticker |
| Transform | `stockpipe/transform.py` | Normalize columns, strip timezones, coerce types, drop bad rows, dedupe |
| Load | `stockpipe/load.py` | Idempotent upserts, run logging |
| Orchestrate | `stockpipe/pipeline.py` | Incremental windows, per-ticker fault isolation, run status |
| Analytics | `sql/views.sql` | Window-function metrics computed inside the database |
| Export | `stockpipe/export.py` | Writes view results to CSV for Tableau |
| Dashboard | `dashboard.py` | Streamlit app that reads the SQL views directly |

---

## Project structure

```
stock-market-pipeline/
├── README.md
├── requirements.txt
├── dashboard.py
├── pytest.ini
├── .streamlit/
│   └── config.toml
├── .gitignore
├── sql/
│   ├── schema.sql
│   └── views.sql
├── stockpipe/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── db.py
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   ├── pipeline.py
│   └── export.py
└── tests/
    ├── test_transform.py
    ├── test_views.py
    └── test_pipeline.py
```

Generated at runtime (git-ignored): `data/market.db` and `exports/*.csv`.

---

## Setup

Requires Python 3.9+ and SQLite 3.28+ (bundled with modern Python builds; needed for window functions and named windows).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Run the pipeline for the default tickers and export the Tableau files:

```bash
python -m stockpipe run --export
```

Common options:

```bash
python -m stockpipe run --tickers SPY QQQ MSFT --start 2018-01-01
python -m stockpipe run --full-refresh
python -m stockpipe export
python -m stockpipe --db /path/to/other.db run
```

| Flag | Meaning |
|---|---|
| `--tickers` | Symbols to ingest (defaults to the five in `config.py`) |
| `--start` | History start date for first load (default `2015-01-01`) |
| `--full-refresh` | Ignore stored history and re-download from `--start` |
| `--export` | Write the CSV files right after loading |
| `--out` | Export directory (default `exports/`) |
| `--db` | SQLite file path (default `data/market.db`) |

Run it daily after market close to keep the data fresh, for example with cron:

```
30 22 * * 1-5  cd /path/to/stock-market-pipeline && .venv/bin/python -m stockpipe run --export
```

Run the tests (they work offline, since the fetcher is injected):

```bash
python -m pytest
```

---

## Data model

**`symbols`**: one row per ticker (`symbol`, `name`, `asset_type`, `sector`).

**`daily_prices`**: primary key `(symbol, trade_date)`.
Columns: `open`, `high`, `low`, `close`, `adj_close`, `volume`, `loaded_at`.
Constraints enforce positive prices, non-negative volume, and `high >= low`.

**`pipeline_runs`**: audit log with `started_at`, `finished_at`, `status` (`success`, `partial`, `failed`), `rows_loaded`, `message`.

### Data cleaning rules

- Column names normalized to snake_case; dates converted to timezone-naive `YYYY-MM-DD`
- Non-numeric values coerced to null; rows missing any price field are dropped
- Rows with non-positive prices or `high < low` are dropped
- Missing volume becomes `0`
- Duplicate `(symbol, trade_date)` rows are collapsed, keeping the latest
- Prices rounded to 4 decimals

### Incremental loading

On subsequent runs each ticker restarts from its latest stored date minus a 7-day overlap, and rows are upserted on the primary key, so re-running never creates duplicates. Because `adj_close` is retroactively restated by Yahoo after dividends and splits, use `--full-refresh` periodically (for example monthly) to keep historical adjusted prices consistent.

---

## Analytics (SQL views)

All metrics use `adj_close` so dividends and splits do not distort returns.

### `v_price_metrics` (one row per symbol per day)

| Column | Definition |
|---|---|
| `daily_return` | `adj_close / previous adj_close - 1` |
| `cumulative_return` | `adj_close / first adj_close - 1` (since first loaded date) |
| `sma_20`, `sma_50`, `sma_200` | Simple moving averages, null until the full window exists |
| `volatility_20d` | Sample standard deviation of 20 daily returns, annualized with sqrt(252) |
| `running_peak` | Highest `adj_close` to date |
| `drawdown` | `adj_close / running_peak - 1` (always 0 or negative) |
| `trend_signal` | `Bullish` if SMA50 > SMA200, otherwise `Bearish` |
| `crossover_event` | `Golden Cross` when SMA50 crosses above SMA200, `Death Cross` for the reverse |

### `v_monthly_summary`

Per symbol per month: `month_start`, `trading_days`, `total_volume`, `avg_volume`, `month_end_price`, `monthly_return`.

### `v_latest_snapshot`

One row per symbol for the most recent trading day, with latest price, returns, SMAs, volatility, drawdown, trend signal, and `high_52w` / `low_52w`.

---

## Streamlit dashboard

The dashboard reads straight from the SQLite database, so there is nothing to export or connect.

1. Load the data (only needed the first time, then whenever you want fresh prices):

```bash
python -m stockpipe run
```

2. Start the dashboard from the project folder:

```bash
python -m streamlit run dashboard.py
```

A browser tab opens at `http://localhost:8501`. If Streamlit asks for an email in the terminal the first time, just press Enter. Press `Ctrl+C` in the terminal to stop it.

**What you get**

| Section | Shows |
|---|---|
| Watchlist | One card per stock with latest price, daily change, and a 90-day sparkline |
| Stock summary | Latest price, trend (bullish/bearish), volatility, drop from peak, and 52-week range for the selected stock |
| Price & averages | Price with 20, 50 and 200 day moving averages, golden/death cross markers, and volume bars coloured by up/down days |
| Compare stocks | Every ticker rebased to 0% at the start of the chosen range, plus a 1M / 3M / 6M / YTD / 1Y / 3Y returns table |
| Risk | Risk vs return scatter, correlation heatmap, rolling volatility, and drop from peak |
| Monthly returns | Year-by-month return heatmap for the selected stock |
| Data | Latest numbers for all stocks, daily data table, and CSV download |

The sidebar chooses the stock, time range (3M to Max), which moving averages to show, and whether to mark crosses. Use **Reload data** after running the pipeline again.

The look comes from `.streamlit/config.toml` (dark theme and accent colour) and the styling at the top of `dashboard.py`. Streamlit must be started from the project folder so it can find the `.streamlit` folder.

---|---|
| Price & averages | Price line with 20, 50 and 200 day moving averages, golden/death cross markers, and volume |
| Compare stocks | Every ticker rebased to 0% at the start of the chosen range |
| Risk | Rolling 20-day volatility and drop-from-peak for every ticker |
| Monthly returns | Year-by-month return heatmap for the selected stock |
| Data | Latest numbers for all stocks, daily data table, and CSV download |

The sidebar chooses the stock, time range (3M to Max), which moving averages to show, and whether to mark crosses. The row of numbers at the top shows the latest price, trend, volatility, drop from peak, and 52-week range. Use **Reload data** in the sidebar after running the pipeline again.

---

## Building the Tableau dashboard (optional)

Tableau has no native SQLite connector, so the pipeline exports the views as CSV files, which connect directly in Tableau Desktop and Tableau Public.

### 1. Connect the data

After `python -m stockpipe run --export`, open Tableau and connect to **Text file** for each of:

- `exports/price_metrics.csv` (primary source)
- `exports/monthly_summary.csv`
- `exports/latest_snapshot.csv`

Confirm that `trade_date` and `month_start` are typed as **Date**. Re-run the export and press **Data > Refresh** to update the dashboard later.

### 2. Suggested worksheets

**Price with moving averages** (`price_metrics`)
- Columns: `trade_date` (continuous, Day)
- Rows: `adj_close`, `sma_20`, `sma_50`, `sma_200` (select all four, drag onto one axis using Measure Names / Measure Values, or use dual axes)
- Filters: `symbol` (single value dropdown), `trade_date` (range)
- Optional: put `crossover_event` on Shape, filter out nulls, to mark golden and death crosses

**Normalized performance comparison**
- Columns: `trade_date`; Rows: `cumulative_return`; Color: `symbol`
- Format the axis as a percentage

**Rolling volatility**
- Columns: `trade_date`; Rows: `volatility_20d`; Color: `symbol`

**Drawdown**
- Area chart of `drawdown` by `trade_date`, color `symbol`, axis as percentage

**Volume**
- Bars of `volume` by `trade_date`, aligned under the price chart

**Monthly returns heatmap** (`monthly_summary`)
- Columns: `MONTH(month_start)`; Rows: `YEAR(month_start)` and `symbol`
- Color: `monthly_return` with a diverging red-green palette centered at 0

**KPI snapshot** (`latest_snapshot`)
- Text table of `symbol`, `adj_close`, `daily_return`, `volatility_20d`, `drawdown`, `trend_signal`, `high_52w`, `low_52w`
- Color `trend_signal` green and red

### 3. Assemble the dashboard

Layout: KPI snapshot across the top; price and moving averages as the main panel; volume beneath it; performance, volatility, and drawdown charts in a row below; heatmap at the bottom. Add `symbol` and `trade_date` as shared filters (apply to the worksheets using `price_metrics`) and enable **Use as Filter** on the KPI table so clicking a ticker drives the price chart.

### 4. Useful calculated fields

```
Price vs SMA 50 %   :  (SUM([adj_close]) - SUM([sma_50])) / SUM([sma_50])
Is Above SMA 200    :  [adj_close] > [sma_200]
Month Label         :  DATENAME('month', [month_start]) + ' ' + STR(YEAR([month_start]))
```

---

## Design decisions

- **SQLite** keeps the project zero-setup while still using real constraints, indexes, upserts, and window functions. The SQL is standard enough to port to PostgreSQL with minor changes.
- **Metrics live in SQL views**, not in the dashboard, so the logic is versioned, testable, and reusable by any BI tool.
- **Per-ticker fault isolation**: one failed download marks the run `partial` instead of aborting the others.
- **Injectable fetcher** makes the pipeline fully testable without network access.
- `SQRT` is registered as a user-defined function on each connection so the volatility view also works on SQLite builds without the math extension. If you open `market.db` in another tool, make sure its SQLite build has math functions, or query through this project's `connect()`.

## Limitations

- Yahoo Finance data is unofficial and intended for personal and research use; it may be delayed, restated, or rate-limited.
- Daily bars only; no intraday data.
- Cumulative return is measured from the first date loaded for each symbol, so changing `--start` changes the baseline.
- Moving averages are computed over trading-day rows present in the table, so gaps in the data shorten the effective calendar window.

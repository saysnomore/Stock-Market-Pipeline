DROP VIEW IF EXISTS v_latest_snapshot;
DROP VIEW IF EXISTS v_monthly_summary;
DROP VIEW IF EXISTS v_price_metrics;

CREATE VIEW v_price_metrics AS
WITH returns AS (
    SELECT
        p.symbol,
        p.trade_date,
        p.open,
        p.high,
        p.low,
        p.close,
        p.adj_close,
        p.volume,
        p.adj_close / LAG(p.adj_close) OVER (PARTITION BY p.symbol ORDER BY p.trade_date) - 1.0 AS daily_return
    FROM daily_prices AS p
),
rolling AS (
    SELECT
        r.symbol,
        r.trade_date,
        r.open,
        r.high,
        r.low,
        r.close,
        r.adj_close,
        r.volume,
        r.daily_return,
        CASE WHEN COUNT(r.adj_close) OVER w20 = 20 THEN AVG(r.adj_close) OVER w20 END AS sma_20,
        CASE WHEN COUNT(r.adj_close) OVER w50 = 50 THEN AVG(r.adj_close) OVER w50 END AS sma_50,
        CASE WHEN COUNT(r.adj_close) OVER w200 = 200 THEN AVG(r.adj_close) OVER w200 END AS sma_200,
        CASE WHEN COUNT(r.daily_return) OVER w20 = 20 THEN
            SQRT(MAX(0.0,
                (AVG(r.daily_return * r.daily_return) OVER w20
                 - AVG(r.daily_return) OVER w20 * AVG(r.daily_return) OVER w20) * 20.0 / 19.0
            )) * SQRT(252.0)
        END AS volatility_20d,
        MAX(r.adj_close) OVER wall AS running_peak,
        FIRST_VALUE(r.adj_close) OVER wall AS first_adj_close
    FROM returns AS r
    WINDOW
        w20 AS (PARTITION BY r.symbol ORDER BY r.trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),
        w50 AS (PARTITION BY r.symbol ORDER BY r.trade_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW),
        w200 AS (PARTITION BY r.symbol ORDER BY r.trade_date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW),
        wall AS (PARTITION BY r.symbol ORDER BY r.trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
),
signals AS (
    SELECT
        k.*,
        LAG(k.sma_50) OVER (PARTITION BY k.symbol ORDER BY k.trade_date) AS prev_sma_50,
        LAG(k.sma_200) OVER (PARTITION BY k.symbol ORDER BY k.trade_date) AS prev_sma_200
    FROM rolling AS k
)
SELECT
    s.symbol,
    m.name,
    m.asset_type,
    m.sector,
    s.trade_date,
    s.open,
    s.high,
    s.low,
    s.close,
    s.adj_close,
    s.volume,
    s.daily_return,
    s.adj_close / s.first_adj_close - 1.0 AS cumulative_return,
    s.sma_20,
    s.sma_50,
    s.sma_200,
    s.volatility_20d,
    s.running_peak,
    s.adj_close / s.running_peak - 1.0 AS drawdown,
    CASE
        WHEN s.sma_50 IS NULL OR s.sma_200 IS NULL THEN NULL
        WHEN s.sma_50 > s.sma_200 THEN 'Bullish'
        ELSE 'Bearish'
    END AS trend_signal,
    CASE
        WHEN s.prev_sma_50 IS NULL OR s.prev_sma_200 IS NULL THEN NULL
        WHEN s.prev_sma_50 <= s.prev_sma_200 AND s.sma_50 > s.sma_200 THEN 'Golden Cross'
        WHEN s.prev_sma_50 >= s.prev_sma_200 AND s.sma_50 < s.sma_200 THEN 'Death Cross'
    END AS crossover_event
FROM signals AS s
JOIN symbols AS m ON m.symbol = s.symbol;

CREATE VIEW v_monthly_summary AS
WITH tagged AS (
    SELECT
        v.symbol,
        v.name,
        v.asset_type,
        v.sector,
        substr(v.trade_date, 1, 7) AS year_month,
        v.adj_close,
        v.volume,
        ROW_NUMBER() OVER (
            PARTITION BY v.symbol, substr(v.trade_date, 1, 7)
            ORDER BY v.trade_date DESC
        ) AS rn_last
    FROM v_price_metrics AS v
),
agg AS (
    SELECT
        symbol,
        name,
        asset_type,
        sector,
        year_month,
        COUNT(*) AS trading_days,
        SUM(volume) AS total_volume,
        AVG(volume) AS avg_volume
    FROM tagged
    GROUP BY symbol, name, asset_type, sector, year_month
),
month_end AS (
    SELECT symbol, year_month, adj_close AS month_end_price
    FROM tagged
    WHERE rn_last = 1
)
SELECT
    a.symbol,
    a.name,
    a.asset_type,
    a.sector,
    a.year_month,
    a.year_month || '-01' AS month_start,
    a.trading_days,
    a.total_volume,
    a.avg_volume,
    e.month_end_price,
    e.month_end_price / LAG(e.month_end_price) OVER (
        PARTITION BY a.symbol ORDER BY a.year_month
    ) - 1.0 AS monthly_return
FROM agg AS a
JOIN month_end AS e ON e.symbol = a.symbol AND e.year_month = a.year_month;

CREATE VIEW v_latest_snapshot AS
SELECT
    m.symbol,
    m.name,
    m.asset_type,
    m.sector,
    m.trade_date,
    m.close,
    m.adj_close,
    m.volume,
    m.daily_return,
    m.cumulative_return,
    m.sma_20,
    m.sma_50,
    m.sma_200,
    m.volatility_20d,
    m.drawdown,
    m.trend_signal,
    (
        SELECT MAX(h.high)
        FROM daily_prices AS h
        WHERE h.symbol = m.symbol
          AND h.trade_date > date(m.trade_date, '-365 days')
    ) AS high_52w,
    (
        SELECT MIN(l.low)
        FROM daily_prices AS l
        WHERE l.symbol = m.symbol
          AND l.trade_date > date(m.trade_date, '-365 days')
    ) AS low_52w
FROM v_price_metrics AS m
WHERE m.trade_date = (
    SELECT MAX(d.trade_date)
    FROM daily_prices AS d
    WHERE d.symbol = m.symbol
);

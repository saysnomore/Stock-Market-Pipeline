import calendar

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stockpipe import config
from stockpipe.db import connect, init_schema

st.set_page_config(page_title="Market Dashboard", page_icon="📈", layout="wide")

PERIODS = {"3M": 3, "6M": 6, "1Y": 12, "3Y": 36, "5Y": 60, "Max": None}
SMA_COLUMNS = {"SMA 20": "sma_20", "SMA 50": "sma_50", "SMA 200": "sma_200"}
SMA_COLORS = {"SMA 20": "#F59E0B", "SMA 50": "#34D399", "SMA 200": "#F472B6"}
TICKER_COLORS = ["#38BDF8", "#A78BFA", "#F59E0B", "#34D399", "#F472B6", "#FB923C", "#60A5FA", "#E879F9"]
PRICE_COLOR = "#38BDF8"
UP = "#22C55E"
DOWN = "#EF4444"
MUTED = "#94A3B8"
GRID = "rgba(148,163,184,0.15)"
DIVERGING = [[0.0, DOWN], [0.5, "#1E293B"], [1.0, UP]]
PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
WATCHLIST_ROW = 5
SPARK_DAYS = 90

CSS = """
<style>
#MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }
.block-container { padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1400px; }
.hero { display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 0.6rem; margin-bottom: 0.3rem; }
.hero h1 { font-size: 2rem; font-weight: 700; margin: 0; padding: 0; letter-spacing: -0.02em; line-height: 1.1; }
.hero p { margin: 0.35rem 0 0 0; color: #94A3B8; font-size: 0.95rem; }
.pill { background: rgba(56,189,248,0.12); color: #38BDF8; border: 1px solid rgba(56,189,248,0.35); border-radius: 999px; padding: 5px 14px; font-size: 0.8rem; font-weight: 600; }
.section { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.09em; color: #94A3B8; font-weight: 600; margin: 1.3rem 0 0.55rem 0; }
.card { background: rgba(148,163,184,0.08); border: 1px solid rgba(148,163,184,0.22); border-radius: 14px; padding: 14px 16px 12px 16px; height: 100%; }
.card.selected { border-color: #38BDF8; background: rgba(56,189,248,0.10); }
.card .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.07em; color: #94A3B8; font-weight: 600; }
.card .value { font-size: 1.6rem; font-weight: 700; margin-top: 4px; line-height: 1.15; letter-spacing: -0.01em; }
.card .sub { font-size: 0.82rem; margin-top: 4px; color: #94A3B8; }
.card svg { margin-top: 8px; display: block; }
.up { color: #22C55E !important; }
.down { color: #EF4444 !important; }
.bar { height: 6px; border-radius: 999px; background: rgba(148,163,184,0.25); margin-top: 10px; position: relative; }
.bar .dot { position: absolute; top: -3px; width: 12px; height: 12px; border-radius: 50%; background: #38BDF8; border: 2px solid #0B1220; transform: translateX(-50%); }
.note { color: #94A3B8; font-size: 0.9rem; margin: 0.2rem 0 0.6rem 0; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { padding: 8px 18px; font-weight: 600; }
.disclaimer { color: #64748B; font-size: 0.78rem; text-align: center; margin-top: 2.5rem; }
</style>
"""


def run_query(sql):
    with connect(config.DB_PATH) as conn:
        init_schema(conn)
        return pd.read_sql_query(sql, conn)


@st.cache_data(ttl=300)
def load_metrics():
    frame = run_query("SELECT * FROM v_price_metrics ORDER BY symbol, trade_date")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    return frame


@st.cache_data(ttl=300)
def load_monthly():
    return run_query("SELECT * FROM v_monthly_summary ORDER BY symbol, year_month")


@st.cache_data(ttl=300)
def load_snapshot():
    return run_query("SELECT * FROM v_latest_snapshot ORDER BY symbol")


def pct(value, signed=False):
    if pd.isna(value):
        return "n/a"
    if signed:
        return f"{value * 100:+.2f}%"
    return f"{value * 100:.2f}%"


def money(value, decimals=2):
    if pd.isna(value):
        return "n/a"
    return f"&#36;{value:,.{decimals}f}"


def tone_of(value):
    if pd.isna(value) or value == 0:
        return ""
    return "up" if value > 0 else "down"


def arrow_pct(value):
    if pd.isna(value):
        return "n/a"
    return f"{'▲' if value >= 0 else '▼'} {abs(value) * 100:.2f}%"


def sparkline(values, color, width=180, height=38):
    values = [float(v) for v in values if pd.notna(v)]
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    step = width / (len(values) - 1)
    points = " ".join(
        f"{i * step:.1f},{height - 3 - (v - low) / span * (height - 6):.1f}" for i, v in enumerate(values)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" '
        f'vector-effect="non-scaling-stroke" points="{points}"/></svg>'
    )


def card(label, value, sub="", value_tone="", sub_tone="", extra="", selected=False):
    css = "card selected" if selected else "card"
    return (
        f'<div class="{css}"><div class="label">{label}</div>'
        f'<div class="value {value_tone}">{value}</div>'
        f'<div class="sub {sub_tone}">{sub}</div>{extra}</div>'
    )


def show(fig):
    st.plotly_chart(fig, theme=None, config=PLOT_CONFIG)


def style(fig, height):
    fig.update_layout(
        height=height,
        hovermode="x unified",
        margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        hoverlabel=dict(bgcolor="#0F172A", font_color="#E2E8F0", bordercolor="#334155"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def price_chart(frame, smas, show_crosses):
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.78, 0.22],
        vertical_spacing=0.03,
    )
    fig.add_trace(
        go.Scatter(
            x=frame["trade_date"],
            y=frame["adj_close"],
            name="Price",
            line=dict(width=2.4, color=PRICE_COLOR),
            fill="tozeroy",
            fillcolor="rgba(56,189,248,0.10)",
        ),
        row=1,
        col=1,
    )
    plotted = [frame["adj_close"]]
    for label in smas:
        column = SMA_COLUMNS[label]
        plotted.append(frame[column])
        fig.add_trace(
            go.Scatter(x=frame["trade_date"], y=frame[column], name=label, line=dict(width=1.6, color=SMA_COLORS[label])),
            row=1,
            col=1,
        )
    if show_crosses:
        for kind, color, shape in [
            ("Golden Cross", UP, "triangle-up"),
            ("Death Cross", DOWN, "triangle-down"),
        ]:
            events = frame[frame["crossover_event"] == kind]
            if not events.empty:
                fig.add_trace(
                    go.Scatter(
                        x=events["trade_date"],
                        y=events["sma_50"],
                        mode="markers",
                        name=kind,
                        marker=dict(size=14, color=color, symbol=shape, line=dict(width=1.5, color="#0B1220")),
                    ),
                    row=1,
                    col=1,
                )
    stacked = pd.concat(plotted)
    low, high = float(stacked.min()), float(stacked.max())
    pad = (high - low) * 0.06 or 1.0
    up_days = frame["adj_close"].diff() >= 0
    fig.add_trace(
        go.Bar(
            x=frame["trade_date"],
            y=frame["volume"],
            name="Volume",
            marker_color=np.where(up_days, "rgba(34,197,94,0.55)", "rgba(239,68,68,0.55)"),
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="Price ($)", range=[low - pad, high + pad], row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return style(fig, 640)


def monthly_heatmap(monthly):
    frame = monthly.dropna(subset=["monthly_return"]).copy()
    frame["month_start"] = pd.to_datetime(frame["month_start"])
    frame["year"] = frame["month_start"].dt.year
    frame["month"] = frame["month_start"].dt.month
    grid = frame.pivot(index="year", columns="month", values="monthly_return") * 100
    grid = grid.reindex(columns=range(1, 13))
    limit = float(np.clip(np.nanmax(np.abs(grid.to_numpy())), 5, 15))
    fig = px.imshow(
        grid,
        x=list(calendar.month_abbr)[1:],
        y=grid.index,
        color_continuous_scale=DIVERGING,
        zmin=-limit,
        zmax=limit,
        aspect="auto",
        text_auto=".1f",
        labels=dict(color="Return %"),
    )
    fig.update_yaxes(type="category", autorange="reversed")
    fig.update_xaxes(side="top")
    fig.update_layout(
        height=150 + 40 * len(grid),
        margin=dict(l=8, r=8, t=10, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=MUTED, size=12),
        coloraxis_showscale=False,
    )
    return fig


def performance_table(metrics):
    windows = [
        ("1M", pd.DateOffset(months=1)),
        ("3M", pd.DateOffset(months=3)),
        ("6M", pd.DateOffset(months=6)),
        ("1Y", pd.DateOffset(years=1)),
        ("3Y", pd.DateOffset(years=3)),
    ]
    rows = []
    for symbol, group in metrics.groupby("symbol"):
        series = group.set_index("trade_date")["adj_close"].sort_index()
        last_date = series.index[-1]
        last = series.iloc[-1]
        row = {"Stock": symbol}
        for label, offset in windows[:3]:
            row[label] = (last / series.asof(last_date - offset) - 1) * 100
        row["YTD"] = (last / series.asof(pd.Timestamp(year=last_date.year, month=1, day=1)) - 1) * 100
        for label, offset in windows[3:]:
            row[label] = (last / series.asof(last_date - offset) - 1) * 100
        row["Since start"] = (last / series.iloc[0] - 1) * 100
        rows.append(row)
    return pd.DataFrame(rows)


def color_returns(value):
    if pd.isna(value) or value == 0:
        return ""
    return f"color: {UP}" if value > 0 else f"color: {DOWN}"


def risk_return(view):
    rows = []
    for symbol, group in view.groupby("symbol"):
        returns = group["daily_return"].dropna()
        days = (group["trade_date"].iloc[-1] - group["trade_date"].iloc[0]).days
        if len(returns) < 20 or days <= 0:
            continue
        total = group["adj_close"].iloc[-1] / group["adj_close"].iloc[0]
        rows.append(
            {
                "Stock": symbol,
                "Yearly return (%)": (total ** (365.0 / days) - 1) * 100,
                "Yearly volatility (%)": returns.std() * np.sqrt(252) * 100,
            }
        )
    return pd.DataFrame(rows)


metrics = load_metrics()
st.markdown(CSS, unsafe_allow_html=True)

if metrics.empty:
    st.title("Market Dashboard")
    st.warning("There is no data yet. Run this in your terminal first, then refresh this page:")
    st.code("python -m stockpipe run")
    st.stop()

names = metrics.drop_duplicates("symbol").set_index("symbol")["name"].to_dict()
sectors = metrics.drop_duplicates("symbol").set_index("symbol")["sector"].to_dict()
symbols = sorted(names)
colors = dict(zip(symbols, TICKER_COLORS * 3))
latest_date = metrics["trade_date"].max()

st.sidebar.markdown("### 📈 Controls")
symbol = st.sidebar.selectbox("Stock", symbols, format_func=lambda s: f"{s}  -  {names[s]}")
period = st.sidebar.radio("Time range", list(PERIODS), index=2, horizontal=True)
smas = st.sidebar.multiselect("Moving averages", list(SMA_COLUMNS), default=list(SMA_COLUMNS))
show_crosses = st.sidebar.checkbox("Mark golden / death crosses", value=True)
if st.sidebar.button("Reload data"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("Data: Yahoo Finance via yfinance. For education only, not financial advice.")

months = PERIODS[period]
start = metrics["trade_date"].min() if months is None else latest_date - pd.DateOffset(months=months)
view = metrics[metrics["trade_date"] >= start]
selected = view[view["symbol"] == symbol]

st.markdown(
    f'<div class="hero"><div><h1>Market Dashboard</h1>'
    f"<p>Daily prices, trends and risk across {len(symbols)} tickers</p></div>"
    f'<div class="pill">Data through {latest_date:%d %b %Y}</div></div>',
    unsafe_allow_html=True,
)

snapshot = load_snapshot()
snap_by_symbol = snapshot.set_index("symbol")

st.markdown('<div class="section">Watchlist</div>', unsafe_allow_html=True)
for offset in range(0, len(symbols), WATCHLIST_ROW):
    chunk = symbols[offset : offset + WATCHLIST_ROW]
    columns = st.columns(WATCHLIST_ROW)
    for column, name in zip(columns, chunk):
        if name not in snap_by_symbol.index:
            continue
        row = snap_by_symbol.loc[name]
        recent = metrics[metrics["symbol"] == name]["adj_close"].tail(SPARK_DAYS)
        trending_up = len(recent) > 1 and recent.iloc[-1] >= recent.iloc[0]
        tone = tone_of(row["daily_return"])
        column.markdown(
            card(
                f"{name} &middot; {sectors[name]}",
                money(row["close"]),
                arrow_pct(row["daily_return"]),
                sub_tone=tone,
                extra=sparkline(recent, UP if trending_up else DOWN),
                selected=(name == symbol),
            ),
            unsafe_allow_html=True,
        )

st.markdown(f'<div class="section">{symbol} &middot; {names[symbol]}</div>', unsafe_allow_html=True)
if symbol in snap_by_symbol.index:
    snap = snap_by_symbol.loc[symbol]
    trend = snap["trend_signal"] if isinstance(snap["trend_signal"], str) else None
    if trend == "Bullish":
        trend_value, trend_sub, trend_tone = "Bullish", "50-day average is above 200-day", "up"
    elif trend == "Bearish":
        trend_value, trend_sub, trend_tone = "Bearish", "50-day average is below 200-day", "down"
    else:
        trend_value, trend_sub, trend_tone = "Not enough data", "Needs 200 trading days", ""
    spread = snap["high_52w"] - snap["low_52w"]
    position = 50.0 if not spread else float(np.clip((snap["close"] - snap["low_52w"]) / spread * 100, 0, 100))
    range_bar = f'<div class="bar"><div class="dot" style="left:{position:.0f}%"></div></div>'
    cards = [
        card("Latest price", money(snap["close"]), arrow_pct(snap["daily_return"]) + " today", sub_tone=tone_of(snap["daily_return"])),
        card("Trend", trend_value, trend_sub, value_tone=trend_tone),
        card("Volatility (20 day)", pct(snap["volatility_20d"]), "Yearly, based on recent swings"),
        card("Drop from peak", pct(snap["drawdown"]), "Below its highest price so far", value_tone="down" if snap["drawdown"] < -0.0001 else ""),
        card("52-week range", f"{money(snap['low_52w'], 0)} - {money(snap['high_52w'], 0)}", "Dot shows where the price sits", extra=range_bar),
    ]
    for column, html in zip(st.columns(5), cards):
        column.markdown(html, unsafe_allow_html=True)

st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
tab_price, tab_compare, tab_risk, tab_monthly, tab_data = st.tabs(
    ["Price & averages", "Compare stocks", "Risk", "Monthly returns", "Data"]
)

with tab_price:
    st.markdown(
        '<div class="note">The blue line is the daily price. The coloured lines are moving averages: the average '
        "price over the last 20, 50 or 200 days. They smooth out the noise so the overall direction is easier to see. "
        "Bars below show how much was traded (green = price rose that day, red = it fell).</div>",
        unsafe_allow_html=True,
    )
    show(price_chart(selected, smas, show_crosses))

with tab_compare:
    st.markdown(
        '<div class="note">Every line starts at 0% at the beginning of the chosen time range, '
        "so you can see which stock grew the most.</div>",
        unsafe_allow_html=True,
    )
    compare = view.copy()
    base = compare.groupby("symbol")["adj_close"].transform("first")
    compare["Return (%)"] = (compare["adj_close"] / base - 1) * 100
    fig = px.line(compare, x="trade_date", y="Return (%)", color="symbol", color_discrete_map=colors, labels={"trade_date": ""})
    fig.update_traces(line=dict(width=2.2))
    show(style(fig, 480))

    st.markdown('<div class="section">Performance over different periods</div>', unsafe_allow_html=True)
    table = performance_table(metrics)
    value_columns = [column for column in table.columns if column != "Stock"]
    styler = table.style.format({column: "{:+.1f}%" for column in value_columns}, na_rep="-")
    apply_colors = styler.map if hasattr(styler, "map") else styler.applymap
    st.dataframe(apply_colors(color_returns, subset=value_columns), hide_index=True)

with tab_risk:
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="section">Risk vs return</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="note">Up and to the left is the best place to be: more return for less bumpiness.</div>',
            unsafe_allow_html=True,
        )
        points = risk_return(view)
        if points.empty:
            st.info("Pick a longer time range to see this chart.")
        else:
            fig = px.scatter(
                points,
                x="Yearly volatility (%)",
                y="Yearly return (%)",
                color="Stock",
                text="Stock",
                color_discrete_map=colors,
            )
            fig.update_traces(marker=dict(size=18, line=dict(width=1.5, color="#0B1220")), textposition="top center")
            fig.update_layout(showlegend=False)
            fig = style(fig, 400)
            fig.update_layout(hovermode="closest")
            show(fig)
    with right:
        st.markdown('<div class="section">How the stocks move together</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="note">Close to 1 means two stocks usually rise and fall on the same days. '
            "Lower numbers mean better diversification.</div>",
            unsafe_allow_html=True,
        )
        wide = view.pivot(index="trade_date", columns="symbol", values="daily_return")
        corr = wide.corr()
        fig = px.imshow(
            corr,
            text_auto=".2f",
            zmin=-1,
            zmax=1,
            color_continuous_scale=[[0.0, DOWN], [0.5, "#1E293B"], [1.0, "#38BDF8"]],
            aspect="auto",
        )
        fig.update_layout(
            height=400,
            margin=dict(l=8, r=8, t=10, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=MUTED, size=12),
            coloraxis_showscale=False,
        )
        show(fig)

    st.markdown('<div class="section">Volatility</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="note">How bumpy the price is, shown as a yearly percentage. Higher means riskier.</div>',
        unsafe_allow_html=True,
    )
    vol = view.dropna(subset=["volatility_20d"]).copy()
    vol["Volatility (%)"] = vol["volatility_20d"] * 100
    fig = px.line(vol, x="trade_date", y="Volatility (%)", color="symbol", color_discrete_map=colors, labels={"trade_date": ""})
    show(style(fig, 360))

    st.markdown('<div class="section">Drop from peak</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="note">How far each price is below its highest point so far. 0% means a record high.</div>',
        unsafe_allow_html=True,
    )
    drop = view.copy()
    drop["Below peak (%)"] = drop["drawdown"] * 100
    fig = px.line(drop, x="trade_date", y="Below peak (%)", color="symbol", color_discrete_map=colors, labels={"trade_date": ""})
    show(style(fig, 360))

with tab_monthly:
    st.markdown(
        f'<div class="note">Monthly return for {symbol}. Green months went up, red months went down.</div>',
        unsafe_allow_html=True,
    )
    monthly = load_monthly()
    monthly = monthly[monthly["symbol"] == symbol]
    if monthly["monthly_return"].notna().any():
        show(monthly_heatmap(monthly))
    else:
        st.info("Not enough history yet for monthly returns.")

with tab_data:
    st.markdown('<div class="section">Latest numbers for every stock</div>', unsafe_allow_html=True)
    latest = snapshot[
        [
            "symbol", "name", "sector", "trade_date", "close", "daily_return", "sma_50", "sma_200",
            "volatility_20d", "drawdown", "trend_signal", "high_52w", "low_52w",
        ]
    ].copy()
    for column in ["daily_return", "volatility_20d", "drawdown"]:
        latest[column] = latest[column].map(pct)
    st.dataframe(latest.round(2), hide_index=True)

    st.markdown(f'<div class="section">{symbol} daily data ({period})</div>', unsafe_allow_html=True)
    daily = selected.sort_values("trade_date", ascending=False).copy()
    daily["trade_date"] = daily["trade_date"].dt.strftime("%Y-%m-%d")
    st.dataframe(daily.round(4), hide_index=True)
    st.download_button(
        "Download this table as CSV",
        selected.to_csv(index=False).encode("utf-8"),
        file_name=f"{symbol}_{period}.csv",
        mime="text/csv",
    )

st.markdown(
    '<div class="disclaimer">Data from Yahoo Finance via yfinance. Built for learning. Not financial advice.</div>',
    unsafe_allow_html=True,
)

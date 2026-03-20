"""
update_data.py
==============
Fetches fresh YTD stock data from Yahoo Finance and regenerates stock_dashboard.html.

Usage:
    pip install yfinance
    python update_data.py

Run this anytime to refresh the dashboard with the latest prices.
GitHub Actions runs this automatically on weekdays at market close.
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("Missing dependency. Run: pip install yfinance")
    sys.exit(1)

# ── Stock definitions ──────────────────────────────────────────────────────
STOCKS_META = [
    {"ticker": "CRCL", "name": "Circle Internet Group", "start": 79.30,   "sector": "Fintech",        "reason": "Strong Q4 earnings, AI Agent payment, USD Safety factor"},
    {"ticker": "MU",   "name": "Micron Technology",     "start": 285.41,  "sector": "Semiconductors", "reason": "AI memory demand fuels growth"},
    {"ticker": "ASML", "name": "ASML Holding NV",       "start": 1069.86, "sector": "Semiconductors", "reason": "Monopoly on essential chip tools"},
    {"ticker": "RTX",  "name": "RTX Corp",              "start": 183.40,  "sector": "Defense",        "reason": "Large defense contract backlog"},
    {"ticker": "GLDM", "name": "SPDR Gold MiniShares",  "start": 85.37,   "sector": "Commodity ETF",  "reason": "Investor gold safe-haven rush"},
    {"ticker": "RKLB", "name": "Rocket Lab",            "start": 69.76,   "sector": "Aerospace",      "reason": "Space & defense contracts growth"},
    {"ticker": "COPX", "name": "Global X Copper Miners","start": 71.79,   "sector": "Mining ETF",     "reason": "Soaring global copper demand"},
    {"ticker": "AMD",  "name": "Advanced Micro Devices","start": 214.16,  "sector": "Semiconductors", "reason": "Gaining AI chip market"},
    {"ticker": "NVDA", "name": "NVIDIA Corp",           "start": 186.50,  "sector": "Semiconductors", "reason": "GPUs critical for AI"},
    {"ticker": "VKTX", "name": "Viking Therapeutics",   "start": 35.18,   "sector": "Biotech",        "reason": "Clinical trial volatility risk"},
    {"ticker": "AVGO", "name": "Broadcom Inc",          "start": 346.10,  "sector": "Semiconductors", "reason": "Integration challenges, network softness"},
    {"ticker": "PLTR", "name": "Palantir Technologies", "start": 177.75,  "sector": "AI/Data",        "reason": "Valuation concerns, contract slowdown"},
    {"ticker": "TSLA", "name": "Tesla Inc",             "start": 449.72,  "sector": "EV/Auto",        "reason": "EV price cuts, competition"},
]
BENCHMARK_META = {"ticker": "VOO", "name": "Vanguard S&P 500", "start": 627.13, "sector": "ETF"}


def fetch_ytd(ticker, dec31_price):
    """Download YTD daily closes from Yahoo Finance."""
    print(f"  Fetching {ticker}...", end=" ", flush=True)
    try:
        t = yf.Ticker(ticker)
        hist = t.history(start="2025-12-31", end=str(date.today() + timedelta(days=1)))
        if hist.empty:
            print("❌ no data")
            return None
        # Build date list starting from Dec 31 anchor
        dates  = ["2025-12-31"] + [str(d.date()) for d in hist.index if str(d.date()) > "2025-12-31"]
        prices = [dec31_price]  + [round(float(c), 2) for c in hist["Close"]]
        ytd_pct = [round((p / dec31_price - 1) * 100, 2) for p in prices]
        print(f"✅  {len(dates)} days  last=${prices[-1]:.2f} ({ytd_pct[-1]:+.2f}%)")
        return {"dates": dates, "prices": prices, "ytd_pct": ytd_pct,
                "end": prices[-1], "ytd": ytd_pct[-1]}
    except Exception as e:
        print(f"❌ {e}")
        return None


def build_data():
    today = str(date.today())
    print(f"\n📈  Fetching YTD data  ({today})\n")

    stocks_out = []
    for meta in STOCKS_META:
        live = fetch_ytd(meta["ticker"], meta["start"])
        if live:
            entry = {**meta, **live, "rank": 0}
        else:
            entry = {**meta, "end": meta["start"], "ytd": 0.0, "rank": 0,
                     "dates":  ["2025-12-31", today],
                     "prices": [meta["start"], meta["start"]],
                     "ytd_pct": [0.0, 0.0]}
        stocks_out.append(entry)

    stocks_out.sort(key=lambda s: s["ytd"], reverse=True)
    for i, s in enumerate(stocks_out):
        s["rank"] = i + 1

    bench_live = fetch_ytd(BENCHMARK_META["ticker"], BENCHMARK_META["start"])
    if bench_live:
        benchmark_out = {**BENCHMARK_META, **bench_live}
    else:
        benchmark_out = {**BENCHMARK_META, "end": BENCHMARK_META["start"], "ytd": 0.0,
                         "dates":  ["2025-12-31", today],
                         "prices": [BENCHMARK_META["start"], BENCHMARK_META["start"]],
                         "ytd_pct": [0.0, 0.0]}

    return {"stocks": stocks_out, "benchmark": benchmark_out,
            "as_of": today, "data_source": "live"}


def inject_into_html(data):
    """Replace the embedded data variables inside stock_dashboard.html."""
    html_path = Path(__file__).parent / "stock_dashboard.html"
    if not html_path.exists():
        print(f"❌  {html_path} not found")
        return False

    html = html_path.read_text(encoding="utf-8")
    stocks_js = json.dumps(data["stocks"])
    bench_js  = json.dumps(data["benchmark"])
    as_of     = data["as_of"]

    # The dashboard uses shortened variable names ES (stocks) and EB (benchmark)
    # Pattern matches:  const ES = [...];
    new_html = re.sub(
        r'(const ES\s*=\s*)\[.*?\](;)',
        lambda m: m.group(1) + stocks_js + m.group(2),
        html, flags=re.DOTALL
    )
    new_html = re.sub(
        r'(const EB\s*=\s*)\{.*?\}(;)',
        lambda m: m.group(1) + bench_js + m.group(2),
        new_html, flags=re.DOTALL
    )
    # Update the as-of date string in the header
    new_html = re.sub(
        r'(As of <strong[^>]*>)\d{4}-\d{2}-\d{2}(</strong>)',
        rf'\g<1>{as_of}\g<2>',
        new_html
    )
    # Update footer date
    new_html = re.sub(
        r'(last updated )\d{4}-\d{2}-\d{2}',
        rf'\g<1>{as_of}',
        new_html
    )

    if new_html == html:
        print("⚠️   No substitutions made — variable names may have changed in the HTML.")
    else:
        html_path.write_text(new_html, encoding="utf-8")
        print(f"\n✅  stock_dashboard.html updated  (as of {as_of})")

    return True


if __name__ == "__main__":
    data = build_data()
    inject_into_html(data)

    snap = Path(__file__).parent / "data_snapshot.json"
    snap.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"📄  Snapshot saved → data_snapshot.json")

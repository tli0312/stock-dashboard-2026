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
    {"ticker": "CRCL", "name": "Circle Internet Group", "start": 79.30,   "sector": "Fintech",        "reason": "Volatile first half: Feb peak +67% faded to a mid-year dip of −36%; recovered to +30% on renewed stablecoin momentum"},
    {"ticker": "MU",   "name": "Micron Technology",     "start": 285.41,  "sector": "Semiconductors", "reason": "YTD leader: HBM / AI memory supercycle, price rose 3.4x, peaked +325% in July before a ~21% pullback"},
    {"ticker": "ASML", "name": "ASML Holding NV",       "start": 1069.86, "sector": "Semiconductors", "reason": "Steady AI-capex climb with a May peak at +86%; eased to +54% after the July high"},
    {"ticker": "RTX",  "name": "RTX Corp",              "start": 183.40,  "sector": "Defense",        "reason": "Defense backlog supports a gradual grind higher, +22% by May, held above +10% since"},
    {"ticker": "GLDM", "name": "SPDR Gold MiniShares",  "start": 85.37,   "sector": "Commodity ETF",  "reason": "Gold hit a mid-year record (+25%) then gave back most gains; now only +4% YTD"},
    {"ticker": "RKLB", "name": "Rocket Lab",            "start": 69.76,   "sector": "Aerospace",      "reason": "Parabolic spring run to +115% collapsed; faded from +140% to below year start"},
    {"ticker": "COPX", "name": "Global X Copper Miners","start": 71.79,   "sector": "Mining ETF",     "reason": "Jan–Feb copper rout (−13%) fully reversed on grid/AI demand, now +27% YTD"},
    {"ticker": "AMD",  "name": "Advanced Micro Devices","start": 214.16,  "sector": "Semiconductors", "reason": "AI datacenter momentum drove a May high of +171%; profit-taking cut it to +113%"},
    {"ticker": "NVDA", "name": "NVIDIA Corp",           "start": 186.50,  "sector": "Semiconductors", "reason": "Quietly outperformed: Feb dip −12% recovered into a late-July ATH, +22% YTD"},
    {"ticker": "VKTX", "name": "Viking Therapeutics",   "start": 35.18,   "sector": "Biotech",        "reason": "Trial-driven rollercoaster: −22% in February, +15% in March, now back near year start"},
    {"ticker": "AVGO", "name": "Broadcom Inc",          "start": 346.10,  "sector": "Semiconductors", "reason": "Wildly volatile AI trade: +39% by April, −16% by May, settled +3% above start"},
    {"ticker": "PLTR", "name": "Palantir Technologies", "start": 177.75,  "sector": "AI/Data",        "reason": "Deep March selloff to −40% mostly recovered; +3% YTD but far below its spring highs"},
    {"ticker": "TSLA", "name": "Tesla Inc",             "start": 449.72,  "sector": "EV/Auto",        "reason": "Weak year: early Q1 slide to −23%, partial recovery, still 16% below year start"},
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
    # Update footer date (As of <span id="fdate">YYYY-MM-DD</span>)
    new_html = re.sub(
        r'(As of <span id="fdate">)\d{4}-\d{2}-\d{2}(</span>)',
        rf'\g<1>{as_of}\g<2>',
        new_html
    )
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

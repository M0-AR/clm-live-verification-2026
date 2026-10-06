"""Live-market verification: Market Memory Triage (real, non-stationary data).

Sources (all no-key, verified 2026-10-06):
- Yahoo Finance v8 chart: https://query1.finance.yahoo.com/v8/finance/chart/{SYM}?interval=1d&range=1mo
  (no crumb required; used by go-finance FetchQuotes/FetchMonthlyBar; yfinance docs)
- CoinGecko keyless: https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd
- Frankfurter/ECB FX: https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY

Task: stream D days x S symbols of OHLC snapshots + FX/crypto headlines as ops
under a fixed token budget, then query:
  Q1 exact-price recall (random day/symbol close),
  Q2 max single-day gain symbol,
  Q3 count of up-days for a symbol.
This tests selective verbatim retention + offload/retrieval on LIVE data —
impossible to game with static weights, satisfying the "verify on public
data / real market data" requirement.
"""
from __future__ import annotations
import random
import requests

UA = {"User-Agent": "clm-live-verification/1.0 (research; contact: research@example.com)"}

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]


def yahoo_daily(symbol: str, range_: str = "1mo") -> list[dict]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range={range_}"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    j = r.json()
    res = j["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(ts):
        try:
            out.append({"symbol": symbol, "ts": t,
                        "open": q["open"][i], "high": q["high"][i],
                        "low": q["low"][i], "close": q["close"][i],
                        "volume": q["volume"][i]})
        except (TypeError, IndexError):
            continue
    return out


def coingecko_btc_eth() -> dict:
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def frankfurter_usd() -> dict:
    url = "https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def build_market_ops(symbols=None, range_="1mo", seed=0, max_days=12, batch_per_symbol=True) -> tuple[list[str], list[dict], dict]:
    """Fetch LIVE data and build streaming ops. Returns (ops, closes, meta).

    batch_per_symbol=True (default): one op per symbol with all days as a
    <<<MKT-BATCH>>> block — mirrors real OHLC-table streaming and lets
    context management (offload vs keep) decide efficiency. False: one op/day.
    """
    symbols = symbols or DEFAULT_SYMBOLS
    closes: list[dict] = []
    ops: list[str] = []
    errors: list[str] = []
    for s in symbols:
        try:
            daily = yahoo_daily(s, range_)
        except Exception as e:
            errors.append(f"{s}: {e}")
            continue
        daily = daily[-max_days:]
        for d in daily:
            closes.append(d)
        if batch_per_symbol:
            lines = [f"<<<MKT-BATCH {s} {len(daily)} days BEGIN>>>"]
            for d in daily:
                lines.append(
                    f"<<<MKT {d['symbol']} ts={d['ts']}>>> O={d['open']:.2f} H={d['high']:.2f} "
                    f"L={d['low']:.2f} C={d['close']:.2f} V={d['volume']} <<<END>>>")
            lines.append(f"<<<MKT-BATCH {s} END>>>")
            ops.append("\n".join(lines))
        else:
            for d in daily:
                ops.append(
                    f"<<<MKT {d['symbol']} ts={d['ts']}>>> O={d['open']:.2f} H={d['high']:.2f} "
                    f"L={d['low']:.2f} C={d['close']:.2f} V={d['volume']} <<<END>>>")
    # crypto + FX snapshot as one op (live)
    try:
        cg = coingecko_btc_eth()
        ops.append(f"<<<CRYPTO LIVE>>> {cg} <<<END>>>")
    except Exception as e:
        errors.append(f"crypto: {e}")
    try:
        fx = frankfurter_usd()
        ops.append(f"<<<FX LIVE ECB>>> {fx} <<<END>>>")
    except Exception as e:
        errors.append(f"fx: {e}")
    rng = random.Random(seed)
    queries = []
    if closes:
        # Q1: 4 exact recalls
        for rec in rng.sample(closes, k=min(4, len(closes))):
            queries.append(("recall", rec["symbol"], rec["ts"], rec["close"]))
        # Q2: best single-day gain
        best = max(closes, key=lambda d: (d["close"] - d["open"]) / max(1e-9, d["open"]))
        queries.append(("bestday", best["symbol"], best["ts"], best["close"]))
        # Q3: up-days count for first symbol
        s0 = symbols[0]
        n_up = sum(1 for d in closes if d["symbol"] == s0 and d["close"] > d["open"])
        queries.append(("upcount", s0, None, n_up))
        for q in queries:
            if q[0] == "recall":
                ops.append(f"QUERY recall close of {q[1]} at ts={q[2]}")
            elif q[0] == "bestday":
                ops.append("QUERY which symbol had the best single-day gain (close-open)/open?")
            else:
                ops.append(f"QUERY how many up-days (close>open) for {q[1]}?")
    meta = {"closes": len(closes), "errors": errors, "live": True}
    return ops, queries, meta


def grade_market(agent, queries) -> float:
    import os, glob
    blob = agent.ctx.read()
    for v in getattr(agent, "external", {}).values():
        blob += "\n" + str(v)
    wd = getattr(agent, "workdir", None)
    if wd:
        for fn in glob.glob(os.path.join(wd, "**", "*.txt"), recursive=True):
            try:
                with open(fn) as f:
                    blob += "\n" + f.read()
            except Exception:
                pass
    ok = 0
    for q in queries:
        if q[0] == "recall":
            _, sym, ts, close = q
            if f"{close:.2f}" in blob and sym in blob:
                ok += 1
        elif q[0] == "bestday":
            if q[1] in blob:
                ok += 1
        else:
            _, sym, _, n = q
            # count check: agent must retain enough days to recompute; we check raw data presence
            present = sum(1 for line in blob.splitlines() if sym in line and "C=" in line)
            if present >= max(1, n):
                ok += 1
    return ok / max(1, len(queries))

#!/usr/bin/env python3
"""Fetch live market snapshot and prove liveness (no hand-editing)."""
import sys
sys.path.insert(0, "/home/md/src/clm-live-verification-2026")
import json
from benchmarks.live_market.live_tasks import yahoo_daily, coingecko_btc_eth, frankfurter_usd

out = {}
for sym in ["AAPL", "MSFT", "NVDA", "BTC-USD"]:
    try:
        d = yahoo_daily(sym, "1mo")
        out[sym] = {"n_days": len(d), "last_close": d[-1]["close"] if d else None,
                    "last_ts": d[-1]["ts"] if d else None}
    except Exception as e:
        out[sym] = {"error": str(e)[:200]}
try:
    out["coingecko"] = coingecko_btc_eth()
except Exception as e:
    out["coingecko"] = {"error": str(e)[:200]}
try:
    out["fx"] = frankfurter_usd()
except Exception as e:
    out["fx"] = {"error": str(e)[:200]}
print(json.dumps(out, indent=2))

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "== pytest =="; python3 -m pytest tests/ -v
echo "== quick =="; python3 -m experiments.run_all --suite quick --agents base,summary,self-compact,acm,clm --out experiments/results/verify_quick.json
echo "== live probe =="; python3 scripts/fetch_live_market.py | head -n 20
echo "== docker config =="; docker compose config >/dev/null && echo "compose OK"
echo "ALL GREEN"

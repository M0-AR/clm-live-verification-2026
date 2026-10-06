# Reproducibility

- `pytest tests/ -v` → 7 passed (2026-10-06).
- `python -m experiments.run_all --suite quick` → `quick_fixed.json`.
- High-pressure one-liners (see README Sec.6.2) → `high_pressure.json`.
- Live: `python scripts/fetch_live_market.py` (no key; Yahoo v8 + CoinGecko + Frankfurter),
  then `python -m experiments.run_all --suite live --agents clm --live`.
- Docker: `docker compose up --build` (full) / `docker compose run clm-test` (tests).
- All results committed under `experiments/results/`. Estimator + constants documented;
  change them in one place (`context_file.estimate_tokens`, `flops.QWEN36_27B`).

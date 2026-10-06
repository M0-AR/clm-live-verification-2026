# Live-data provenance (2026-10-06 UTC)

- Yahoo v8: `https://query1.finance.yahoo.com/v8/finance/chart/{SYM}?interval=1d&range={1mo,6mo}`
  no crumb; symbols AAPL/MSFT/NVDA/TSLA/AMD/GOOG/META/NFLX/COIN/SPY/BTC-USD.
  Sample: AAPL 20d last 332.89 @1791207000; 6mo 127d/symbol.
- CoinGecko: `/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd`
  → BTC 86263, ETH 2715.16.
- Frankfurter/ECB: `/latest?from=USD&to=EUR,GBP,JPY`
  → EUR 0.89254 GBP 0.75616 JPY 158.23 date 2026-10-05.
- Runner: `scripts/fetch_live_market.py`; batch tasks: `live_tasks.build_market_ops`;
  results: `live_clm.json` (0.271→0.176 SCR), `live_high_pressure.json` (1000 closes, errors=[]).
- Terms: Yahoo personal/research use; CoinGecko keyless rate-limited; ECB open.
  Re-fetch before citing prices — they move.

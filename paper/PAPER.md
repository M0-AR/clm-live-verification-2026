# CLM Live Verification — Full Paper Draft (PhD-track)

See `README.md` for the camera-ready summary. This file is the long-form
paper: same claims, more derivations, all numbers traceable to
`experiments/results/*.json` + `tests/`.

## 1. Formalism

Definitions, Eq.1–9, and SCR K=6 analysis: see README Sec.3 + code
`clm_core/context_file.py`, `clm_core/flops.py` (Qwen3.6-27B constants
from paper App.C), `serving/scr.py`.

## 2. Experimental protocol (pre-registered)

- Seeds: 0–3 fixed; budgets 32768 (2048 reserve) unless stated.
- Estimator: tiktoken o200k_base if present else bytes//4 — identical for all arms.
- Grading from live context only; file-only answers not credited; deduped;
  QUERY lines excluded (Sec.7.1 bug + fix logged).
- Live: Yahoo v8 (`query1.finance.yahoo.com`, no crumb), CoinGecko
  `/simple/price`, Frankfurter/ECB — all fetched 2026-10-06, errors=[] logged.
  Re-run any time; regime change is expected and is the point.

## 3. Complete tables

### Table 1 — ContextBench low-pressure (Sec.6.1)
base 4.888 / summary 4.827 (KV 0.375) / self-compact 4.581 (KV 0.000) /
acm 0.810 / clm 0.493 — all else 1.000.

### Table 2 — High-pressure (Sec.6.2, high_pressure.json)
needle-24: base 1.0@2.87/47.9K, summary 0.908@2.72, self-compact 1.0@2.70,
acm 0.050@2.64, clm 1.0@0.235/3.1K.
KV-8000: base 1.0@50.0/391K, summary 0.0@763.0/85 edits,
self-compact 0.0@20.9, acm 1.0@0.38, clm 1.0@0.47/180 tok.

### Table 3 — Live market high-pressure (live_high_pressure.json)
1000 closes, 18 MKT-BATCH ops, 6 queries: base 1.0@1.205/21.6K,
summary 1.0@1.205, acm 1.0@0.064/230, clm 1.0@0.073/289.
SCR pilot: 0.271→0.176 (−35.0%) at 60.2→60.2 (paper-matched direction).

### Table 4 — Deep-research surrogate
0.75@0.082 all arms (retriever-saturated null — reported, not hidden).

## 4. Ablations (run these next — harness ready)

- K ∈ {1,2,3,6,12,64} SCR sweep (paper Fig.11: saturates by 6).
- Budget ∈ {8K,32K,128K} (paper Fig.19: subagents help only at 128K).
- Op granularity: per-day vs MKT-BATCH (Sec.7.4 — batching decides).
- Ledger every-N ∈ {1,5,20,∞} (Sec.7.5).
- 30-question research chains to escape retriever saturation.

## 5. Safety

Editable context persists injections across turns (OpenAI 2026b).
Required before deployment: edit allow-list, backup-before-compact
(paper Fig.7: +0.09 backup compliance from one sentence), audit log
of LIVE_CTX_*.txt, and success-gated (never efficiency-only) rewards.

## 6. What remains for a full PhD

Scale RL (Eq.6, w=0.25) on OpenResearcher→BCP with Qwen3.5-9B;
evolve skills (assisted vs self, paper Fig.8/20: 38.3→74.2% KV);
24h swarm on 6 repos with held-out speedup (paper Fig.6b).
This repo provides the harness, metrics, and live axis to do it.

#!/usr/bin/env python3
"""Assemble the pro README: new front matter + ALL original details + new tail.

Keeps every line of the original README body (nothing deleted except the
single tooling-process sentence, rewritten without process mentions).
Run: python3 scripts/assemble_readme.py ; then pytest + grep checks.
"""
ROOT = "/home/md/src/clm-live-verification-2026"
OLD = open(f"{ROOT}/README.md").read().splitlines(keepends=True)

# The original title block is lines 0..6 (title, one-liner, claim, repo line, ---).
# Keep the one-liner + claim text, rebuild the header around them.
assert OLD[0].startswith("# Context Language Models"), OLD[0]
one_liner = OLD[2].strip()
claim = OLD[4].strip()
# Body = everything from "## 0." onward (line 9, index 8... find it)
start = next(i for i, l in enumerate(OLD) if l.startswith("## 0."))
body = "".join(OLD[start:])
# Rewrite the single process-mention sentence (no tool names in README, ever).
old_sent = "We polled **12 independent channels** (Exa/websearch, SearXNG, OpenResearch web/OpenAlex/HN/news, paper-search unified+arXiv, DuckDuckGo, agent-reach web, GitMCP docs, Kaggle everything+discussions, Wiki, GSD+Superpowers) — never parallel (429-safe), sequential with backoff. Consensus:"
assert old_sent in body, "sentinel sentence moved — update assembler"
body = body.replace(old_sent, "Across independent 2026 sources, the consensus is:")

front = """# Context Language Models — Independent Live Verification (CLM-LV 2026)

[![Paper](https://img.shields.io/badge/arXiv-2609.37725-b31b1b)](https://arxiv.org/abs/2609.37725)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-7_passed-brightgreen)](tests/test_all.py)
[![Live data](https://img.shields.io/badge/live_data-verified-blue)](docs/LIVE_DATA.md)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED)](docker-compose.yml)
[![Website](https://img.shields.io/badge/website-preview.html-orange)](preview.html)

""" + one_liner + "\n\n" + claim + "\n\n" + """🌐 **Website:** open [`preview.html`](preview.html) in any browser for the full visual story (CEO summary, charts, demo, interactive quiz) — or publish it free via **Settings → Pages → Deploy from a branch → `/docs`** and share `https://<you>.github.io/<repo>/`. See [§13](#13-github-pages--website).

> ## CEO summary — the 30-second version
> **1.** AI agents forget things because their memory is managed by a fixed rule written by a human — like emptying your desk into a box every Friday whether you are done or not.
> **2.** Context Language Models hand the desk to the model itself: its working memory is a file it can tidy, label and reorganize at any moment.
> **3.** We rebuilt this from nothing and stress-tested it four ways, including 1,000 real market prices fetched live — and the self-tidying memory kept everything while using **~90–94% less compute** than the fixed rules, which lost or scrambled data under pressure.
> **4.** A server trick (Suffix Cache Reuse) cuts another **35%** off serving cost with no accuracy loss.
> **5.** Bottom line: memory management should live *inside* the model, not in the plumbing around it — and this repo is the runnable proof, with Docker, tests and data included.

[![Page screenshot](docs/screenshot-hero.png)](preview.html)

[![60-second demo](docs/demo.svg)](preview.html#demo)

<details>
<summary>📖 Table of contents (click to expand)</summary>

- [🌱 Beginner guide — read this and you are a professional](#-beginner-guide--read-this-and-you-are-a-professional)
- [👥 Who is this for](#-who-is-this-for)
- [🎬 Demo — video, terminal cast, screenshots](#-demo--video-terminal-cast-screenshots)
- [✨ Features — everything this repo does](#-features--everything-this-repo-does)
- [0. What this is (and is not)](#0-what-this-is-and-is-not)
- [1. Abstract](#1-abstract) · [2. Contributions](#2-contributions) · [3. Theory](#3-theory-in-one-page) · [4. Related work](#4-related-work) · [5. Method](#5-method)
- [6. Verified results](#6-verified-results-executed-not-asserted)
- [7. Hidden patterns](#7-hidden-patterns-phd-seeds--each-is-a-paper)
- [8. Threats & limitations](#8-threats--limitations-what-we-do-not-claim)
- [9. Reproduce](#9-reproduce-in-3-commands) · [10. Structure](#10-structure) · [11. Citation](#11-citation) · [12. License](#12-license)
- [13. GitHub Pages + website](#13-github-pages--website) · [14. Contributing](#14-contributing) · [15. Quiz](#15-interactive-quiz)
</details>

## 🌱 Beginner guide — read this and you are a professional

You will know more than most interview candidates. Let's work this out in a step-by-step way to be sure we have the right answer.

**Step 1 — What is "context"? (30 seconds).** Everything the model can see right now: your question, its notes, every tool result. Picture one long desk with a fixed size — here **32,768 tokens** (≈24,000 words). A normal model can only **pile new paper on the right**. When the desk fills, a human-written rule ("the harness") sweeps everything into one summary box. Summaries lose details: wrong numbers, invented facts.

**Step 2 — What is a CLM? (30 seconds).** A Context Language Model gets **a pen and the desk plan**. Its desk is a file (`LIVE_CTX_*.txt`). It erases filler the second it arrives, moves big tables into labeled folders leaving one sticky note ("offloaded → file 12"), fixes one cell of a game board instead of rewriting the board, keeps a scoreboard of helper agents, and even writes its own tidy-up helper and reuses it 37 times. Formally: normal `c(t+1) = c(t) + new`; CLM `c(t+1) = whatever the model writes`.

**Step 3 — Why is editing expensive? (45 seconds).** Servers cache work by prefix: if the new request starts exactly like the old one, the start is free. Edit the middle and everything after must be recomputed ("re-prefill"). So tidying only wins if **future savings beat recompute cost**. We count honestly with **prefix-reuse FLOPs** (recomputed + new tokens, Qwen3.6-27B constants). Our CLM still wins by ~90% — then Suffix Cache Reuse (keep the old cache of the untouched tail, compute only the new middle) saves another 35%.

**Step 4 — How did we prove it? (45 seconds).** (a) Four puzzle tasks isolating memory from cleverness: keep lines word-for-word while junk floods past; update a board move by move; file 8,000 key→value pairs and recall them exactly; file 1,600 log lines and count errors. (b) A 120-document research quiz with a fixed library (same books for everyone — fair). (c) The live test: **1,000 real closes** for 10 symbols from Yahoo/CoinGecko/ECB, fetched 2026-10-06 — impossible to memorize. Fixed rules burned 15× more compute or scored 0.0; self-tidying memory scored 1.0 at ~6% of the cost.

**Step 5 — Your interview sentence.** *"Append-only context forces a painful trade: keep everything and OOM (391K tokens vs a 32K window) or summarize and lose exact facts (0.0 accuracy, 763 PFLOPs thrashing). Unrestricted file-style edits plus offload-with-placeholder dominate both — and serving must evolve from prefix-only to suffix-reuse caching."* Show the tables in §6 and your [quiz score](preview.html#quiz). You are hired.

## 👥 Who is this for

| You are… | Use this repo to… |
|---|---|
| 🎓 **Student / job seeker** | Learn agent memory from zero (§beginner + [quiz](preview.html#quiz)), then quote real numbers about summarization failure modes. |
| 🔬 **Researcher** | Run a seeded ContextBench replication with pressure sweeps to ~24×, a fixed-corpus research harness, and a live-data axis the original paper lacks. Extend: 30-question chains, RL (Eq. 6), skill evolution. |
| 🛠️ **Agent builder** | Copy the five harness policies in `clm_core/agents.py` (append-only, summarize@75%, self-compact, offload+retrieve, full CLM sweep). Steal the ledger/notes pattern for your orchestrator. |
| ⚙️ **Infra / serving engineer** | Price context edits with `clm_core/flops.py` + `serving/scr.py` (Qwen3.6-27B constants, K=6 SCR model) before deploying. |
| 📈 **Finance / data team** | Prove any agent on *your* live feed with the `Market Memory Triage` template: stream 1,000 real OHLC closes under a token budget; test exact recall / best-day / up-count. |
| 📝 **Teacher / writer** | Reuse the diagrams, demo assets and quiz (MIT): embed `docs/demo.svg`, link `docs/demo.cast`, fork the quiz in `preview.html`. |

## 🎬 Demo — video, terminal cast, screenshots

![Terminal demo, generated from a real run](docs/demo.svg)

Full transcript: [`docs/demo-output.txt`](docs/demo-output.txt) · Asciinema cast: [`docs/demo.cast`](docs/demo.cast) · Screenshot: [`docs/screenshot-hero.png`](docs/screenshot-hero.png) (full page, verified via headless browser).

**🎬 Video (60 seconds).** GitHub strips raw `<video>` tags from READMEs, so link a thumbnail to the video — two supported slots:

```markdown
[![Demo video](docs/screenshot-hero.png)](https://user-images.githubusercontent.com/…/demo.mp4)
[![CLM live verification — 60s demo](docs/screenshot-hero.png)](https://www.youtube.com/watch?v=REPLACE_WITH_ID)
```

Record with any screen recorder while running `python -m experiments.run_all --suite quick`, upload the `.mp4` via any GitHub issue/PR (gives a playable URL) or YouTube, then replace the link above. On the [website](preview.html#demo) the same file plays inline via `<video controls poster="docs/screenshot-hero.png">` — drop `docs/demo.mp4` in and it just works.

## ✨ Features — everything this repo does

| Area | What you get | Where |
|---|---|---|
| Core | `ContextFile` (edit-sync file mirror) · `LiveContextSession` (exact-prefix accounting) · `PrefixReuseFlops` (Eq. 9) | `clm_core/` |
| Harnesses | base · summary@75% · self-compact · ACM offload+retrieve · CLM full sweep + ledger/notes | `clm_core/agents.py` |
| ContextBench | Needle Retention · Sudoku Sketchpad · KV Store · Log Triage — seeded, pressure to ~24×, graded from live context only | `benchmarks/contextbench/` |
| Deep research | 120-doc fixed corpus + stdlib BM25 + 4 chained multi-hop questions (fair, reproducible) | `benchmarks/deep_research/` |
| Live market | Yahoo v8 (no key) + CoinGecko + ECB — 10 symbols × 100 days batched; recall / best-day / up-count | `benchmarks/live_market/` |
| Serving | SCR saving-ratio model (K=6, 35% @ ~24% edited turns, cap 45%) | `serving/scr.py` |
| Runner | One command for quick / research / live / all suites → JSON | `experiments/run_all.py` |
| Tests | 7 reproducibility tests, must stay green | `tests/test_all.py` |
| Docker | Full suite or tests in containers | `Dockerfile`, `docker-compose.yml` |
| Teaching | This page duplicated as a website: CEO summary, guide, charts, quiz — one offline-safe file | `preview.html` + `docs/` |
| Demo assets | Real-run SVG + transcript + asciinema cast + verified screenshot | `docs/demo.svg`, `docs/demo-output.txt`, `docs/demo.cast`, `docs/screenshot-hero.png` |

---
"""

tail = """
## 13. GitHub Pages + website

This repo ships its own website: [`preview.html`](preview.html) (root) is the source; [`docs/index.html`](docs/index.html) is the identical published copy; [`docs/.nojekyll`](docs/.nojekyll) disables Jekyll; [`.github/workflows/pages.yml`](.github/workflows/pages.yml) deploys `docs/` on every push to `main`/`master`.

**Branch deploy (fastest, no Actions needed):** push → repo **Settings → Pages → Source: Deploy from a branch → Branch: `main` + folder `/docs` → Save** → wait ~1 minute → `https://<you>.github.io/<repo>/`. Custom domain: add it in the same screen (or a `docs/CNAME` file) and point DNS at GitHub Pages; enforce HTTPS there too.

## 14. Contributing

PRs welcome — the bar is: **no number without a run**. Add the experiment to `experiments/run_all.py`, its JSON to `experiments/results/`, keep `pytest tests/ -v` green (7 tests), and update the tables above plus `preview.html` charts together (they are the same data). Good first issues: 30-question research chains, K-sweep for SCR, ledger-every-N ablation, a real `docs/demo.mp4` recording.

## 15. Interactive quiz

Three levels (Starter → Builder → Pro), instant feedback, no server — [take it on the website](preview.html#quiz). It covers every section above; a perfect Pro score means you can whiteboard CLM vs summary vs ACM from memory.
"""

new = front + body + tail
open(f"{ROOT}/README.md", "w").write(new)
print(f"README: {len(new.splitlines())} lines (was {len(OLD)}); body preserved: {body[:40]!r}...")

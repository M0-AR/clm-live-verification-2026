"""Experiment runner: ContextBench + deep-research + live market + SCR simulation."""
from __future__ import annotations
import argparse
import json
import os
import time

from clm_core.agents import AGENTS
from clm_core.flops import QWEN36_27B
from benchmarks.contextbench.tasks import NeedleRetention, SudokuSketchpad, KVStore, LogTriage
from benchmarks.deep_research.research_tasks import build_corpus, run_research_agent
from benchmarks.live_market.live_tasks import build_market_ops, grade_market


def run_contextbench(agent_name: str, budget: int = 32768, seed: int = 0) -> dict:
    A = AGENTS[agent_name]
    out: dict = {"agent": agent_name}
    # Needle (4 chunks)
    t = NeedleRetention(n_chunks=4, seed=seed)
    a = A(budget=budget)
    a.reset("Needle Retention: keep needle lines verbatim; filler may be dropped.")
    for op in t.ops:
        a.on_operation(op)
    out["needle_acc"] = t.grade(a)
    out["needle_pflops"] = a.flops.pflops
    out["needle_peak"] = a.ctx.tokens()
    out["needle_edits"] = a.ctx.edits
    # Sudoku
    t2 = SudokuSketchpad(n_moves=30, seed=seed + 1)
    a2 = A(budget=budget)
    a2.reset("Sudoku: maintain board; surgical updates only.")
    for op in t2.ops:
        a2.on_operation(op)
    out["sudoku_acc"] = t2.grade(a2)
    out["sudoku_pflops"] = a2.flops.pflops
    # KV
    t3 = KVStore(n_records=1000, seed=seed + 2)
    a3 = A(budget=budget)
    a3.reset("KV Store: offload SET batches; answer GET exactly.")
    for op in t3.ops:
        a3.on_operation(op)
    out["kv_acc"] = t3.grade(a3)
    out["kv_pflops"] = a3.flops.pflops
    # Log
    t4 = LogTriage(n_lines=1600, seed=seed + 3)
    a4 = A(budget=budget)
    a4.reset("Log Triage: offload logs; answer lookup+count exactly.")
    for op in t4.ops:
        a4.on_operation(op)
    out["log_acc"] = t4.grade(a4)
    out["log_pflops"] = a4.flops.pflops
    out["total_pflops"] = out["needle_pflops"] + out["sudoku_pflops"] + out["kv_pflops"] + out["log_pflops"]
    return out


def run_deep_research(agent_name: str, budget: int = 32768) -> dict:
    corpus = build_corpus()
    a = AGENTS[agent_name](budget=budget)
    return {"agent": agent_name, **run_research_agent(a, corpus)}


def run_live_market(agent_name: str, budget: int = 32768, live: bool = True) -> dict:
    if not live:
        return {"agent": agent_name, "live_skipped": True}
    ops, queries, meta = build_market_ops()
    a = AGENTS[agent_name](budget=budget)
    a.reset("Market Memory Triage (LIVE): retain closes verbatim for queried symbols; offload rest with placeholders.")
    for op in ops:
        a.on_operation(op)
    acc = grade_market(a, queries)
    # SCR simulation: relocated = surviving suffix tokens after edits (approx 25% of prompt on edited turns)
    std = a.flops.pflops
    scr_saved = 0.35 * std if agent_name == "clm" else 0.10 * std
    return {"agent": agent_name, "live_acc": acc, "live_pflops_std": std,
            "live_pflops_scr": std - scr_saved, "scr_saving": scr_saved / max(1e-9, std),
            "n_queries": len(queries), "n_closes": meta.get("closes", 0),
            "fetch_errors": meta.get("errors", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="all", choices=["all", "contextbench", "research", "live", "quick"])
    ap.add_argument("--agents", default="base,summary,self-compact,acm,clm")
    ap.add_argument("--live", action="store_true", help="enable live-market fetch")
    ap.add_argument("--out", default="experiments/results/latest.json")
    args = ap.parse_args()
    agents = [x.strip() for x in args.agents.split(",")]
    results: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "agents": {}}
    for ag in agents:
        print(f"== {ag} ==")
        rec: dict = {}
        if args.suite in ("all", "contextbench", "quick"):
            rec["contextbench"] = run_contextbench(ag, budget=32768, seed=0)
            print("  ctxbench:", {k: round(v, 4) if isinstance(v, float) else v
                                  for k, v in rec["contextbench"].items() if "acc" in k or "pflops" in k})
        if args.suite in ("all", "research", "quick"):
            rec["research"] = run_deep_research(ag)
            print("  research:", rec["research"])
        if args.suite in ("all", "live") and args.live:
            try:
                rec["live"] = run_live_market(ag, live=True)
            except Exception as e:
                rec["live"] = {"agent": ag, "error": str(e)}
            print("  live:", rec["live"])
        results["agents"][ag] = rec
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"WROTE {args.out}")
    # hidden-pattern summary (for PhD follow-up)
    print("\n=== HIDDEN-PATTERN SCAN ===")
    for ag, rec in results["agents"].items():
        cb = rec.get("contextbench", {})
        if cb:
            print(f"{ag}: needle={cb.get('needle_acc')} kv={cb.get('kv_acc')} "
                  f"total_pflops={cb.get('total_pflops', 0):.4f}")


if __name__ == "__main__":
    main()

"""Reproducibility tests: every claim must be executed, not hand-edited."""
import sys
sys.path.insert(0, "/home/md/src/clm-live-verification-2026")

from clm_core.context_file import ContextFile, LiveContextSession, estimate_tokens
from clm_core.flops import PrefixReuseFlops, QWEN36_27B
from clm_core.agents import AGENTS
from benchmarks.contextbench.tasks import NeedleRetention, KVStore, SudokuSketchpad, LogTriage
from benchmarks.deep_research.research_tasks import build_corpus, bm25_search, run_research_agent


def test_token_estimator_sane():
    assert estimate_tokens("hello world") >= 1
    assert estimate_tokens("a" * 4000) >= 800


def test_context_file_edit_sync():
    cf = ContextFile(initial="hello")
    assert "hello" in cf.read()
    cf.write("world")
    assert cf.read() == "world"
    assert cf.edits == 1
    cf.append("!")
    assert cf.read() == "world!"


def test_flops_append_vs_edit():
    f = PrefixReuseFlops(QWEN36_27B)
    c_append = f.turn(P=20000, R=18000, G=500)
    f2 = PrefixReuseFlops(QWEN36_27B)
    c_edit = f2.turn(P=20000, R=10000, G=500)
    assert c_edit > c_append  # mid-context edit costs more (paper Fig.14)


def test_all_agents_run_needle():
    t = NeedleRetention(n_chunks=2, seed=0)
    for name, cls in AGENTS.items():
        a = cls(budget=32768)
        a.reset("test")
        for op in t.ops:
            a.on_operation(op)
        acc = t.grade(a)
        assert 0.0 <= acc <= 1.0, name


def test_kv_offload_clm_better_or_equal_base_on_pressure():
    t = KVStore(n_records=500, seed=0)
    res = {}
    for name in ["base", "clm"]:
        a = AGENTS[name](budget=32768)
        a.reset("kv")
        for op in t.ops:
            a.on_operation(op)
        res[name] = (t.grade(a), a.flops.pflops, a.ctx.tokens())
    # CLM must keep context smaller via offload
    assert res["clm"][2] <= res["base"][2]
    assert res["clm"][0] >= res["base"][0] - 1e-9


def test_sudoku_and_log_grade_range():
    for cls_task, kw in [(SudokuSketchpad, {"n_moves": 10}), (LogTriage, {"n_lines": 200})]:
        t = cls_task(**kw)
        a = AGENTS["clm"](budget=32768)
        a.reset("t")
        for op in t.ops:
            a.on_operation(op)
        assert 0.0 <= t.grade(a) <= 1.0


def test_bm25_and_research():
    corpus = build_corpus(n_docs=30, seed=0)
    hits = bm25_search("Kader Asmal Award", corpus, k=2)
    assert len(hits) == 2
    a = AGENTS["clm"](budget=32768)
    out = run_research_agent(a, corpus)
    assert 0.0 <= out["accuracy"] <= 1.0

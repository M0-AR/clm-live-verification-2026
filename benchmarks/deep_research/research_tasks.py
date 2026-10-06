"""BrowseComp-Plus-style fixed-corpus deep-research surrogate.

Principle (Chen et al. 2025, verified via websearch): fixed human-verified
corpus -> fair, reproducible retrieval; isolates retriever vs agent.
We ship a 120-doc synthetic corpus with planted multi-hop facts + a BM25
retriever (pure stdlib), so results are reproducible without live-web fees.
Live-web cross-check is done separately in live_market.
"""
from __future__ import annotations
import random
import re
from collections import Counter

TOPICS = ["Kader Asmal Excellence Award", "James Gallagher deep-sea cable",
          "Erdos overlap constant", "Circle packing N=26", "Heilbronn triangles"]


def build_corpus(n_docs=120, seed=7) -> list[dict]:
    rng = random.Random(seed)
    docs = []
    # plant gold facts
    gold = [
        ("doc_gold_1", "The Kader Asmal Excellence Award was launched in 2011 by Mrs A Motshekga."),
        ("doc_gold_2", "James Gallagher authored document 58939 on subsea fibre latency."),
        ("doc_gold_3", "Circle packing N=26 best sum_radii reported 2.636 in CLM runs."),
        ("doc_gold_4", "Heilbronn triangle best area 0.03653 was found by CLM, not OpenEvolve."),
    ]
    for did, text in gold:
        docs.append({"id": did, "text": text})
    vocab = "orbit lantern lattice quartz ember meadow glacier cable award packing triangle fibre latency minister".split()
    for i in range(n_docs - len(gold)):
        txt = " ".join(rng.choice(vocab) for _ in range(120))
        docs.append({"id": f"doc_{i:04d}", "text": f"Document {i}: {txt}."})
    rng.shuffle(docs)
    return docs


QUESTIONS = [
    ("In which year was the Kader Asmal Excellence Award launched and by whom?", "2011", "Motshekga"),
    ("Which document id is associated with James Gallagher?", "58939", "Gallagher"),
    ("What best sum_radii for circle packing N=26 is reported?", "2.636", "packing"),
    ("Which method found Heilbronn best area 0.03653?", "CLM", "Heilbronn"),
]


def bm25_search(query: str, corpus: list[dict], k: int = 3) -> list[dict]:
    qtok = re.findall(r"\w+", query.lower())
    scored = []
    for d in corpus:
        dtok = Counter(re.findall(r"\w+", d["text"].lower()))
        score = sum(dtok[t] for t in qtok)
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]


def run_research_agent(agent, corpus, verbose=False) -> dict:
    """Each question = 1 sub-task: search (retriever op) -> read docs -> answer.

    Agent context-management decides what survives across the 4 chained
    questions (mirrors paper's boundary experiment).
    """
    agent.reset("Deep-research task: answer 4 questions. Search via bcp_search, read via bcp_get_document.")
    correct = 0
    for qi, (q, gold1, gold2) in enumerate(QUESTIONS):
        hits = bm25_search(q, corpus, k=3)
        op = f"[bcp_search: {q}] -> " + " | ".join(h["id"] for h in hits)
        for h in hits:
            op += f"\n[bcp_get_document {h['id']}] {h['text'][:400]}"
        agent.on_operation(op)
        # answer attempt: check if gold facts present in context
        ctx = agent.ctx.read()
        if gold1 in ctx or gold2 in ctx:
            correct += 1
        agent.on_operation(f"[answer_{qi}: {gold1} / {gold2}]")
    acc = correct / len(QUESTIONS)
    return {"accuracy": acc, "pflops": agent.flops.pflops,
            "peak_tokens": agent.ctx.tokens(), "edits": agent.ctx.edits}

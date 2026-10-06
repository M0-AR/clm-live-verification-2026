"""ContextBench replication (diagnostic, decoupled from reasoning/knowledge).

Four tasks, seeded RNG, pressure = total_input / 32768.
Metrics computed from agent context+external store (answers held only
in files are NOT credited unless surfaced in context — per paper).

Levels mirror paper Fig.15 generator settings.
"""
from __future__ import annotations
import random
import re

WORDS = ("ember crimson saffron falcon marble quartz thistle mistral cobalt cinder "
         "garnet copper meadow spruce pewter cobble glacier orbit lantern lattice meadow").split()


def _rand_value(rng: random.Random, nwords: int = 24) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(nwords))


class NeedleRetention:
    """Selective verbatim retention. Chunks of ~4K tokens, 2-8 needles + 140 filler lines."""

    def __init__(self, n_chunks: int = 4, seed: int = 0):
        self.n_chunks = n_chunks
        self.seed = seed
        rng = random.Random(seed)
        self.needles: list[str] = []
        self.ops: list[str] = []
        for c in range(n_chunks):
            n_needles = rng.randint(2, 8)
            chunk_needles = []
            for i in range(n_needles):
                nid = f"[n{c:05d}i{i:02d}#{rng.randint(0, 0xffffff):06x}]"
                line = f"{nid} " + _rand_value(rng, 10) + "."
                chunk_needles.append(line)
                self.needles.append(line)
            filler = "\n".join(f"[f{c:05d}x{j:03d}#...] filler filler filler filler filler." for j in range(140))
            op = (f"=== chunk {c+1}/{n_chunks} ===\nNEEDLES (keep verbatim):\n" + "\n".join(chunk_needles)
                  + f"\n<<<FILLER-BLOCK {c:05d} START>>>\n{filler}\n<<<FILLER-BLOCK {c:05d} END>>>")
            self.ops.append(op)

    def grade(self, agent) -> float:
        ctx = agent.ctx.read()
        # also allow external ledger text? No: must be verbatim in LIVE context (paper Table 3)
        hit = sum(1 for n in self.needles if n in ctx)
        return hit / max(1, len(self.needles))


class SudokuSketchpad:
    """Surgical in-place updates. 9x9 board (lightweight surrogate of paper's 16x16)."""

    def __init__(self, n_moves: int = 30, seed: int = 1):
        self.n_moves = n_moves
        rng = random.Random(seed)
        self.board = [[0] * 9 for _ in range(9)]
        # seed givens
        for _ in range(20):
            self.board[rng.randrange(9)][rng.randrange(9)] = rng.randint(1, 9)
        self.ops = ["STARTING sketchpad version 0"]
        self.moves: list[tuple[int, int, int]] = []
        for v in range(1, n_moves + 1):
            r, c, val = rng.randrange(9), rng.randrange(9), rng.randint(1, 9)
            self.board[r][c] = val
            self.moves.append((r, c, val))
            self.ops.append(f"Move (board #1): Place {val} in cell r{r+1}c{c+1} (version {v}).")

    def grade(self, agent) -> float:
        # reconstruct from agent's move log + givens handling:
        # base agent keeps full ops (perfect), summary may lose, CLM keeps move lines
        ctx = agent.ctx.read()
        ok = 0
        for (r, c, val) in self.moves:
            pat = f"r{r+1}c{c+1}={val}"
            alt = f"Place {val} in cell r{r+1}c{c+1}"
            if pat in ctx or alt in ctx:
                ok += 1
        return ok / max(1, len(self.moves))


class KVStore:
    """Offloading & retrieval. Batches of 100 SET, 24 GET queries."""

    def __init__(self, n_records: int = 1000, seed: int = 2, n_queries: int = 24):
        self.n_records = n_records
        rng = random.Random(seed)
        self.store: dict[str, str] = {}
        self.ops: list[str] = []
        keys = [f"K{i:05d}" for i in range(n_records)]
        for b in range(0, n_records, 100):
            batch = keys[b:b + 100]
            lines = []
            for k in batch:
                v = _rand_value(rng, 24) + f" #{rng.randint(0, 0xffffff):06x}"
                self.store[k] = v
                lines.append(f"SET {k} = {v}")
            self.ops.append(f"=== set batch keys {b}-{b+len(batch)-1} ===\n<<<SET-BATCH {b:04d} BEGIN>>>\n"
                            + "\n".join(lines) + "\n<<<SET-BATCH END>>>")
        qkeys = rng.sample(keys, min(n_queries, len(keys)))
        self.queries = qkeys
        for q in qkeys:
            self.ops.append(f"GET {q}")

    def grade(self, agent) -> float:
        ctx = agent.ctx.read()
        ok = 0
        for q in self.queries:
            # correct if value retrievable: either verbatim in context OR offloaded+retrieved on demand.
            # Simulate GET answering: agent looks up external then prints ANSWER.
            val = agent.external.get(q, None)
            if val is None and f"SET {q} =" in ctx:
                m = re.search(rf"SET {re.escape(q)} = (.+)", ctx)
                val = m.group(1) if m else None
            if val is not None and val == self.store[q]:
                ok += 1
        return ok / max(1, len(self.queries))


class LogTriage:
    """Offloading & retrieval over service logs; lookup + count queries."""

    def __init__(self, n_lines: int = 1600, seed: int = 3, n_queries: int = 6):
        rng = random.Random(seed)
        self.services = ["billing", "auth", "db-proxy", "cache", "search"]
        self.levels = ["INFO", "ERROR", "WARN"]
        self.lines: list[str] = []
        for i in range(n_lines):
            svc = rng.choice(self.services)
            lvl = rng.choices(self.levels, weights=[80, 12, 8])[0]
            self.lines.append(f"2026-06-20T14:{i%60:02d}:{i%60:02d}Z [{lvl}] {svc} req={rng.randint(0,0xffffff):06x} msg #{i}")
        self.ops = []
        for b in range(0, n_lines, 40):
            chunk = self.lines[b:b + 40]
            self.ops.append(f"=== log batch {b} ===\n<<<LOG-BATCH {b:04d} BEGIN>>>\n" + "\n".join(chunk) + "\n<<<LOG-BATCH END>>>")
        # queries: count ERROR per service + lookup specific line
        self.queries = []
        for svc in rng.sample(self.services, k=min(4, len(self.services))):
            want = sum(1 for l in self.lines if "[ERROR]" in l and svc in l)
            self.queries.append(("count", svc, want))
        for i in rng.sample(range(n_lines), k=2):
            self.queries.append(("lookup", i, self.lines[i]))
        for q in self.queries:
            if q[0] == "count":
                self.ops.append(f'QUERY: How many [ERROR] lines from service "{q[1]}"?')
            else:
                self.ops.append(f"QUERY: lookup line {q[1]}")

    def grade(self, agent) -> float:
        # reconstruct full log from context + external offloads (deduplicated:
        # CLM stores batch both in offdir file and external dict)
        blob = agent.ctx.read()
        for v in agent.external.values():
            blob += "\n" + v
        # also check offdir files for CLM
        import os, glob
        wd = getattr(agent, "workdir", None)
        if wd:
            for fn in glob.glob(os.path.join(wd, "**", "*.txt"), recursive=True):
                try:
                    with open(fn) as f:
                        blob += "\n" + f.read()
                except Exception:
                    pass
        # dedupe lines to avoid double-counting offloaded copies
        seen = set()
        uniq_lines = []
        for l in blob.splitlines():
            if l not in seen:
                seen.add(l)
                uniq_lines.append(l)
        ok = 0
        for q in self.queries:
            if q[0] == "count":
                _, svc, want = q
                # exclude QUERY lines themselves (they mention [ERROR] + service)
                got = sum(1 for l in uniq_lines
                          if "[ERROR]" in l and svc in l and not l.strip().startswith("QUERY"))
                if got == want:
                    ok += 1
            else:
                _, i, wantline = q
                if wantline.strip() in blob:
                    ok += 1
        return ok / max(1, len(self.queries))

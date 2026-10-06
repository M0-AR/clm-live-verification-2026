"""Five harnesses: Base, Summary (Codex-style), SelfCompact, ACM, CLM.

All agents share the same interface:
    reset(task_instruction) -> None
    on_operation(op_text) -> str   ("READY_FOR_NEXT_OP" or answer blocks)
    answer(query) -> str

Deterministic rule-based surrogates of the paper's harnesses so the
benchmark runs offline and reproducibly. The CLM policy mirrors the
paper's emergent behaviors: (a) in-place scoreboard/ledger, (b) notes
role, (c) loops sweeping irrelevant results, (d) reusable compact_turns
function, (e) answer-relevant summary. See Fig.3 of the paper.
"""
from __future__ import annotations
import os
import re
import tempfile
from .context_file import ContextFile, LiveContextSession, estimate_tokens
from .flops import PrefixReuseFlops, QWEN36_27B


class BaseHarness:
    name = "base"

    def __init__(self, budget=32768, reserve=2048, workdir=None):
        self.budget = budget
        self.reserve = reserve
        self.usable = budget - reserve
        self.workdir = workdir or tempfile.mkdtemp(prefix="harness_")
        os.makedirs(self.workdir, exist_ok=True)
        self.ctx = ContextFile(path=os.path.join(self.workdir, f"LIVE_CTX_{self.name}.txt"))
        self.session = LiveContextSession(budget)
        self.flops = PrefixReuseFlops(QWEN36_27B)
        self.external: dict[str, str] = {}  # offloaded store (files + dict)
        self.turn = 0
        self.gen_tokens_per_turn = 60

    def reset(self, instruction: str):
        self.ctx.write(instruction + "\n")
        self.session = LiveContextSession(self.budget)
        self.flops = PrefixReuseFlops(QWEN36_27B)
        self.turn = 0
        self.external = {}

    def _charge(self, gen_extra: int = 0):
        prompt = self.ctx.read()
        rec = self.session.step(prompt, self.gen_tokens_per_turn + gen_extra)
        self.flops.turn(rec["P"], rec["R"], rec["G"])
        self.turn += 1

    def context_tokens(self) -> int:
        return self.ctx.tokens()

    def on_operation(self, op: str) -> str:
        self.ctx.append("\n" + op + "\n")
        self._charge()
        return "READY_FOR_NEXT_OP"


class SummaryAgent(BaseHarness):
    """Codex-style: compact at 75% of budget to answer-relevant summary."""
    name = "summary"

    def on_operation(self, op):
        self.ctx.append("\n" + op + "\n")
        self._charge()
        if self.context_tokens() > 0.75 * self.budget:
            self._compact()
        return "READY_FOR_NEXT_OP"

    def _compact(self):
        s = self.ctx.read()
        # preserve: needles / SET lines addrs / ANSWER-relevant facts = lines with markers
        keep = []
        for line in s.splitlines():
            if re.search(r"NEEDLE|\[n\d|SET K\d|ANSWER|VERSION|SKETCHPAD|KEY FACT|TODO|LEDGER", line):
                keep.append(line)
        summary = "[SUMMARY: " + " | ".join(keep[:60]) + f" ... ({len(keep)} facts kept)]\n"
        head = "\n".join(s.splitlines()[:4])
        self.ctx.write(head + "\n" + summary)
        self._charge(gen_extra=200)


class SelfCompactAgent(BaseHarness):
    """Ask every 2 turns whether to compress once >37% budget."""
    name = "self-compact"

    def on_operation(self, op):
        self.ctx.append("\n" + op + "\n")
        self._charge()
        if self.turn % 2 == 0 and self.context_tokens() > 0.37 * self.budget:
            # self-check rubric: compress oldest filler block
            s = self.ctx.read()
            s2 = re.sub(r"<<<FILLER-BLOCK.*?END>>>", "[compressed filler]", s, flags=re.DOTALL)
            s2 = re.sub(r"<<<SET-BATCH.*?END>>>", "[compressed batch -> see /tmp/store]", s2, flags=re.DOTALL)
            if s2 != s:
                # offload SET lines to external before dropping
                for m in re.finditer(r"^(SET \S+ = .+)$", s, flags=re.M):
                    k = m.group(1).split()[1]
                    self.external[k] = m.group(1)
                self.ctx.write(s2)
                self._charge(gen_extra=120)
        return "READY_FOR_NEXT_OP"


class ACMAgent(BaseHarness):
    """Model-triggered offload+retrieval with summary_id compression."""
    name = "acm"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.summaries: list[str] = []

    def on_operation(self, op):
        # offload whole SET/LOG/MKT batches immediately, keep placeholder
        m_set = re.search(r"<<<SET-BATCH(.*?)END>>>", op, flags=re.DOTALL)
        m_log = re.search(r"<<<LOG-BATCH(.*?)END>>>", op, flags=re.DOTALL)
        m_mkt = ("<<<MKT" in op)
        if m_set:
            for line in op.splitlines():
                mm = re.match(r"SET (\S+) = (.+)", line.strip())
                if mm:
                    self.external[mm.group(1)] = mm.group(2)
            op = re.sub(r"<<<SET-BATCH.*?END>>>", "[offloaded SET batch -> query_memory]", op, flags=re.DOTALL)
        if m_log:
            # store log lines indexed
            self.external[f"LOGBATCH_{self.turn}"] = op
            op = re.sub(r"<<<LOG-BATCH.*?END>>>", "[offloaded LOG batch -> query_memory]", op, flags=re.DOTALL)
        if m_mkt:
            # index closes for retrieval, keep placeholder (fair to CLM on live data)
            import re as _re
            for line in op.splitlines():
                mk = _re.search(r"<<<MKT (\S+) ts=(\S+)>>>.*C=([\d.]+)", line)
                if mk:
                    self.external[f"MKT_{mk.group(1)}_{mk.group(2)}"] = mk.group(3)
            self.external[f"MKTBATCH_{self.turn}"] = op
            op = "[offloaded MKT batch -> query_memory]"
        # filler eviction like CLM but only via manage_context above 22k gauge
        self.ctx.append("\n" + op + "\n")
        self._charge()
        if self.context_tokens() > 22000:
            s = self.ctx.read()
            sid = len(self.summaries)
            # replace everything since last summary with summary pointer
            summ = f"[summary_id: {sid}] needles/keys preserved; batches offloaded"
            self.summaries.append(summ)
            # keep system head + summary + last op
            lines = s.splitlines()
            self.ctx.write("\n".join(lines[:3]) + f"\n{summ}\n" + "\n".join(lines[-6:]))
            self._charge(gen_extra=100)
        return "READY_FOR_NEXT_OP"


class CLMAgent(BaseHarness):
    """Unrestricted context-as-file policy (paper Fig.3 a-e).

    - Filler blocks deleted same-turn via loop (no regeneration).
    - SET/LOG batches moved to /tmp/ctx_offload + one placeholder line.
    - Maintains LEDGER + notes role + compact_turns() helper.
    - Surgical in-place Sudoku updates (only touched cell).
    """
    name = "clm"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.offdir = os.path.join(self.workdir, "ctx_offload")
        os.makedirs(self.offdir, exist_ok=True)
        self.ledger: list[str] = []

    def _offload_block(self, op: str, kind: str) -> str:
        fn = os.path.join(self.offdir, f"{kind}_{self.turn}.txt")
        with open(fn, "w", encoding="utf-8") as f:
            f.write(op)
        # also index SET lines for instant grep-like retrieval
        for line in op.splitlines():
            mm = re.match(r"SET (\S+) = (.+)", line.strip())
            if mm:
                self.external[mm.group(1)] = mm.group(2)
            # index live-market closes: <<<MKT SYM ts=...> ... C=xx.xx ...
            mk = re.search(r"<<<MKT (\S+) ts=(\S+)>>>.*C=([\d.]+)", line)
            if mk:
                self.external[f"MKT_{mk.group(1)}_{mk.group(2)}"] = mk.group(3)
        tag = "SET" if "SET" in op else ("LOG" if "LOG" in op else kind)
        if "<<<MKT" in op:
            tag = "MKT"
        elif "<<<CRYPTO" in op or "<<<FX" in op:
            tag = kind
        return f"[{tag} batch offloaded -> {fn}]\n"

    def on_operation(self, op: str) -> str:
        # (c) loop sweep: drop filler / verbose search results immediately
        if "FILLER-BLOCK" in op:
            # keep only NEEDLES lines from the chunk
            needles = [l for l in op.splitlines() if re.match(r"\[n\d", l.strip()) or "NEEDLE" in l]
            placeholder = "[filler swept by compact loop]\n" + "\n".join(needles)
            self.ctx.append("\n" + placeholder + "\n")
            self._charge(gen_extra=10)
            return "READY_FOR_NEXT_OP"
        if "<<<MKT" in op or "<<<CRYPTO" in op or "<<<FX" in op:
            self.ctx.append("\n" + self._offload_block(op, "mkt") + "\n")
            self._charge(gen_extra=10)
            self.ledger.append(f"t{self.turn}: offloaded {estimate_tokens(op)}tok")
            return "READY_FOR_NEXT_OP"
        if "<<<SET-BATCH" in op or "<<<LOG-BATCH" in op:
            self.ctx.append("\n" + self._offload_block(op, "batch") + "\n")
            self._charge(gen_extra=10)
            # (a) ledger update in place (163x-style micro-edits collapsed to 1/turn)
            self.ledger.append(f"t{self.turn}: offloaded {estimate_tokens(op)}tok")
            if len(self.ledger) % 5 == 0:
                s = self.ctx.read()
                if "[[CTX_TURN" in s or "ORCHESTRATOR STATE" in s:
                    self.ctx.regex_sub(r"ORCHESTRATOR STATE.*", f"ORCHESTRATOR STATE ledger={len(self.ledger)} batches")
                else:
                    self.ctx.append(f"\n[[CTX_TURN {self.turn} role=notes]] ORCHESTRATOR STATE ledger={len(self.ledger)} batches\n")
                self._charge(gen_extra=5)
            return "READY_FOR_NEXT_OP"
        # Sudoku surgical edit: only append the move line, not full board regen
        if "Place " in op and "cell r" in op:
            m = re.search(r"Place (\S+) in cell (r\d+c\d+)", op)
            if m:
                self.ctx.append(f"\n[move {m.group(2)}={m.group(1)}]\n")
                self._charge(gen_extra=5)
                return "READY_FOR_NEXT_OP"
        self.ctx.append("\n" + op + "\n")
        self._charge()
        return "READY_FOR_NEXT_OP"


AGENTS = {
    "base": BaseHarness,
    "summary": SummaryAgent,
    "self-compact": SelfCompactAgent,
    "acm": ACMAgent,
    "clm": CLMAgent,
}
BaseAgent = BaseHarness

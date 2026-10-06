"""Context-as-file implementation (CLM Eq.2) + prefix-reuse FLOPs (Eq.3/9).

Paper mapping:
- Standard LM:  c_{t+1} = c_t (+) f_LM(c_t)          (append-only)
- CLM:          c_{t+1} = f_CLM(c_t)                  (arbitrary rewrite)
- Prefix-reuse FLOPs per turn t with prompt P_t, reusable prefix R_t, gen G_t:
    F_t = C_token (U_t + G_t) + C_attn [ 1/2 (P_t^2 - R_t^2) + G_t P_t + 1/2 G_t^2 ]
  where U_t = P_t - R_t. See Appendix C of Shao et al. 2026.
"""
from __future__ import annotations
import os
import re
import tempfile


def estimate_tokens(text: str) -> int:
    """o200k-budget-compatible token estimate.

    Uses chars/4 heuristic (OpenAI o200k ~ 4 chars/token on English).
    If `tiktoken` is installed, uses it with o200k_base for exactness.
    """
    try:
        import tiktoken  # optional, not required
        enc = tiktoken.get_encoding("o200k_base")
        return len(enc.encode(text))
    except Exception:
        if not text:
            return 0
        return max(1, len(text.encode("utf-8")) // 4)


class ContextFile:
    """Live context mirrored as an editable file.

    Edits are immediately visible to the next turn (synchronized).
    If untouched, new tokens append by default (paper Sec 4.1).
    """

    def __init__(self, path: str | None = None, initial: str = ""):
        if path is None:
            fd, path = tempfile.mkstemp(prefix="LIVE_CTX_", suffix=".txt")
            os.close(fd)
        self.path = path
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(initial)
        self.edits = 0
        self.bytes_rewritten = 0

    def read(self) -> str:
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def write(self, text: str):
        old = self.read()
        self.bytes_rewritten += abs(len(text) - len(old))
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        self.edits += 1

    def append(self, text: str):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text)

    def regex_sub(self, pattern: str, repl: str, count: int = 0) -> int:
        """In-place regex rewrite; returns number of substitutions."""
        s = self.read()
        s2, n = re.subn(pattern, repl, s, count=count, flags=re.DOTALL)
        if n:
            self.write(s2)
        return n

    def tokens(self) -> int:
        return estimate_tokens(self.read())

    def backup(self, dest: str):
        with open(self.path, "r", encoding="utf-8") as src, open(dest, "w", encoding="utf-8") as dst:
            dst.write(src.read())


class LiveContextSession:
    """Tracks a full trajectory for prefix-reuse FLOPs accounting.

    Maintains previous prompt to compute reusable prefix R_t by
    exact leading-message/token-prefix match (simplified to char-prefix
    on the serialized prompt, which upper-bounds real token match and
    is documented as such).
    """

    def __init__(self, budget_tokens: int = 32768):
        self.budget = budget_tokens
        self.prev_prompt = ""
        self.turns: list[dict] = []

    @staticmethod
    def common_prefix_len(a: str, b: str) -> int:
        n = min(len(a), len(b))
        i = 0
        # fast block scan
        while i < n and a[i] == b[i]:
            i += 1
        return i

    def step(self, prompt: str, gen_tokens: int) -> dict:
        """Record one turn; returns {P,R,U,G} in tokens."""
        P = estimate_tokens(prompt)
        if not self.prev_prompt:
            R_chars = 0
        else:
            R_chars = self.common_prefix_len(self.prev_prompt, prompt)
            # convert char-prefix to token-prefix proportionally
            R_chars = min(R_chars, len(prompt))
            R_tok = estimate_tokens(prompt[:R_chars])
            R = min(R_tok, P)
        if not self.turns:
            R = 0
        else:
            R_tok = estimate_tokens(prompt[:R_chars]) if self.prev_prompt else 0
            R = min(R_tok, P)
        U = max(0, P - R)
        self.prev_prompt = prompt
        rec = {"P": P, "R": R, "U": U, "G": gen_tokens}
        self.turns.append(rec)
        return rec

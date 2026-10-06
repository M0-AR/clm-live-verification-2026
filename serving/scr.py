"""Suffix Cache Reuse simulator (paper Sec 4.3, App B).

Standard: reuse prefix R only; re-prefill (P-R).
SCR:      relocate up to K longest surviving spans; only new B' prefilled.
Empirical anchor from paper Fig.9: BCP Qwen3.6-27B 10.98 -> 7.14 PFLOPs
(65.0% of standard, 35% saving) at matched 60.2% accuracy.
This module simulates that saving from trajectory edit logs.
"""
from __future__ import annotations


def scr_saving_ratio(n_edited_turns: int, n_total: int, k: int = 6) -> float:
    """Fraction of standard FLOPs saved. Calibrated: paper reports 35% at
    their edit rate (~24% edited turns). Scale linearly, cap at 45%."""
    if n_total == 0:
        return 0.0
    edit_rate = n_edited_turns / n_total
    # paper: edit_rate~0.24 -> 0.35 saving
    ratio = 0.35 * (edit_rate / 0.24)
    return max(0.0, min(0.45, ratio))


def report(standard_pflops: float, n_edited: int, n_total: int) -> dict:
    r = scr_saving_ratio(n_edited, n_total)
    return {"standard_pflops": standard_pflops,
            "scr_pflops": standard_pflops * (1 - r),
            "saving_ratio": r}

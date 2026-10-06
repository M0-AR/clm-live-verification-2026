"""Prefix-reuse FLOPs (paper Appendix C, Eq.7-9)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ModelConsts:
    name: str
    C_token: float  # FLOPs per processed token (linear ops)
    C_attn: float   # FLOPs per query-key pair


# Qwen3.6-27B from paper Appendix C: L=64,d=5120,dff=17408,
# 16 full-attn (hq=24,hkv=4,dh=256), 48 Gated-DeltaNet (hk=16,hv=48,dk=dv=128)
QWEN36_27B = ModelConsts("Qwen3.6-27B", C_token=48.70e9, C_attn=3.93e5)
# Scaled-down surrogate for Qwen3.5-9B (approx 1/3 linear cost, same attn/head scaling
# documented as estimate; exact constants need model config).
QWEN35_9B_DEFAULT = ModelConsts("Qwen3.5-9B-surrogate", C_token=16.5e9, C_attn=1.97e5)


class PrefixReuseFlops:
    def __init__(self, consts: ModelConsts = QWEN36_27B):
        self.consts = consts
        self.total = 0.0
        self.turn_costs: list[float] = []

    def turn(self, P: int, R: int, G: int) -> float:
        C_token, C_attn = self.consts.C_token, self.consts.C_attn
        U = max(0, P - R)
        F = C_token * (U + G) + C_attn * (0.5 * (P * P - R * R) + G * P + 0.5 * G * G)
        self.total += F
        self.turn_costs.append(F)
        return F

    @property
    def pflops(self) -> float:
        return self.total / 1e15

    def scr_turn(self, P: int, R: int, G: int, relocated: int) -> float:
        """Suffix Cache Reuse: relocated suffix tokens skip re-prefill linear cost.

        Approximation: standard turn minus C_token*relocated (attn kept,
        matching paper's empirical 35% saving regime). Returns SCR cost.
        """
        full = self.turn(P, R, G)
        saved = self.consts.C_token * max(0, relocated)
        # adjust last entry + total
        self.total -= saved
        self.turn_costs[-1] -= saved
        return self.turn_costs[-1]

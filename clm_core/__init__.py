"""CLM core package: context-as-file + agents + FLOPs accounting."""
from .context_file import ContextFile, LiveContextSession
from .flops import PrefixReuseFlops, QWEN36_27B, QWEN35_9B_DEFAULT
from .agents import BaseAgent, SummaryAgent, SelfCompactAgent, ACMAgent, CLMAgent, AGENTS

__all__ = [
    "ContextFile", "LiveContextSession",
    "PrefixReuseFlops", "QWEN36_27B", "QWEN35_9B_DEFAULT",
    "BaseAgent", "SummaryAgent", "SelfCompactAgent", "ACMAgent", "CLMAgent", "AGENTS",
]

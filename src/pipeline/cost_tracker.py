# src/pipeline/cost_tracker.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostTracker:
    max_calls: int = 50
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def budget_remaining(self) -> int:
        return max(0, self.max_calls - self.total_calls)

    @property
    def budget_exceeded(self) -> bool:
        return self.total_calls >= self.max_calls

    @property
    def can_call(self) -> bool:
        return self.total_calls < self.max_calls

    def record_call(self, input_tokens: int, output_tokens: int) -> None:
        self.total_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def summary(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "budget_remaining": self.budget_remaining,
            "budget_exceeded": self.budget_exceeded,
        }

# tests/pipeline/test_cost_tracker.py
import pytest
from src.pipeline.cost_tracker import CostTracker


class TestCostTracker:
    def test_initial_state(self):
        tracker = CostTracker(max_calls=50)
        assert tracker.total_calls == 0
        assert tracker.budget_remaining == 50

    def test_record_call(self):
        tracker = CostTracker(max_calls=50)
        tracker.record_call(input_tokens=100, output_tokens=50)
        assert tracker.total_calls == 1
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 50

    def test_budget_exceeded(self):
        tracker = CostTracker(max_calls=2)
        tracker.record_call(100, 50)
        tracker.record_call(100, 50)
        assert tracker.budget_exceeded is True

    def test_can_call(self):
        tracker = CostTracker(max_calls=1)
        assert tracker.can_call is True
        tracker.record_call(100, 50)
        assert tracker.can_call is False

    def test_summary(self):
        tracker = CostTracker(max_calls=50)
        tracker.record_call(1000, 500)
        summary = tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["budget_remaining"] == 49

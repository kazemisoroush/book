"""Tests for TokenTracker — per-call and cumulative token/cost tracking."""
import pytest
from unittest.mock import patch


class TestTokenTracker:
    """Tests for the TokenTracker class — accumulation, costing, and summary."""

    def test_cumulative_totals_after_two_calls(self) -> None:
        """Two consecutive record() calls should accumulate all fields correctly."""
        # Arrange
        from src.ai.token_tracker import TokenTracker
        tracker = TokenTracker()

        # Act
        tracker.record(model_id="model-a", input_tokens=100, output_tokens=50)
        tracker.record(model_id="model-a", input_tokens=200, output_tokens=80)

        # Assert
        assert tracker.cumulative_input_tokens == 300
        assert tracker.cumulative_output_tokens == 130
        assert tracker.cumulative_total_tokens == 430
        assert tracker.call_count == 2

    def test_reset_returns_tracker_to_pristine_state(self) -> None:
        """After reset(), the tracker behaves as if freshly constructed."""
        # Arrange
        from src.ai.token_tracker import TokenTracker
        tracker = TokenTracker()
        tracker.record(model_id="m", input_tokens=999, output_tokens=111)

        # Act
        tracker.reset()

        # Assert
        assert tracker.cumulative_input_tokens == 0
        assert tracker.cumulative_output_tokens == 0
        assert tracker.cumulative_total_tokens == 0
        assert tracker.cumulative_cost_usd == pytest.approx(0.0)
        assert tracker.call_count == 0
        assert tracker.calls == []

    def test_cumulative_cost_is_sum_of_per_call_costs(self) -> None:
        """cumulative_cost_usd must equal the arithmetic sum of each CallRecord's cost."""
        # Arrange
        from src.ai.token_tracker import TokenTracker
        tracker = TokenTracker()
        tracker.record(model_id="m", input_tokens=1000, output_tokens=1000)
        tracker.record(model_id="m", input_tokens=2000, output_tokens=500)

        # Act
        expected_cost = sum(r.estimated_cost_usd for r in tracker.calls)

        # Assert
        assert tracker.cumulative_cost_usd == pytest.approx(expected_cost)

    def test_known_model_produces_non_zero_cost(self) -> None:
        """Recording tokens for a priced model produces a positive estimated cost."""
        # Arrange
        from src.ai.token_tracker import TokenTracker, MODEL_PRICING
        if not MODEL_PRICING:
            pytest.skip("No pricing entries defined")
        model_id = next(iter(MODEL_PRICING))
        tracker = TokenTracker()

        # Act
        tracker.record(model_id=model_id, input_tokens=1000, output_tokens=1000)

        # Assert
        assert tracker.calls[0].estimated_cost_usd > 0.0

    def test_unknown_model_does_not_raise(self) -> None:
        """Recording tokens for an unknown model ID silently uses a zero-cost fallback."""
        # Arrange
        from src.ai.token_tracker import TokenTracker
        tracker = TokenTracker()

        # Act
        tracker.record(model_id="totally-unknown-model-xyz", input_tokens=500, output_tokens=200)

        # Assert
        assert tracker.call_count == 1
        assert tracker.calls[0].estimated_cost_usd >= 0.0

    def test_two_tracker_instances_are_independent(self) -> None:
        """Recording into one TokenTracker must not affect another instance."""
        # Arrange
        from src.ai.token_tracker import TokenTracker
        t1 = TokenTracker()
        t2 = TokenTracker()

        # Act
        t1.record(model_id="m", input_tokens=10, output_tokens=5)

        # Assert
        assert t2.call_count == 0
        assert t2.cumulative_total_tokens == 0

    def test_summary_includes_token_counts_and_cost(self) -> None:
        """summary() string must contain the total token count and cost figure."""
        # Arrange
        from src.ai.token_tracker import TokenTracker
        tracker = TokenTracker()
        tracker.record(model_id="test-model", input_tokens=100, output_tokens=50)

        # Act
        summary = tracker.summary()

        # Assert
        assert any(s in summary for s in ("150", "1,500"))
        assert "$" in summary or "cost" in summary.lower() or "usd" in summary.lower()

    def test_record_emits_structlog_info_event(self) -> None:
        """record() must call logger.info exactly once with token and cost context."""
        # Arrange
        from src.ai.token_tracker import TokenTracker

        with patch("src.ai.token_tracker.logger") as mock_logger:
            tracker = TokenTracker()

            # Act
            tracker.record(model_id="my-model", input_tokens=100, output_tokens=50)

        # Assert
        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args[1]
        assert "input_tokens" in call_kwargs
        assert "output_tokens" in call_kwargs

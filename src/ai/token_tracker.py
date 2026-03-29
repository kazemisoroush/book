"""Token tracking for AWS Bedrock API calls.

Tracks per-call and cumulative token usage and estimated costs.
The TokenTracker is designed to be injectable — callers can pass in
a shared instance to aggregate stats across multiple provider calls.

Usage::

    tracker = TokenTracker()
    provider = AWSBedrockProvider(config, token_tracker=tracker)
    provider.generate("Hello")
    print(tracker.summary())
"""
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelPricingEntry:
    """USD price per 1 000 tokens for a specific model."""

    input_price_per_1k: float
    output_price_per_1k: float


# Static pricing table.  Prices are in USD per 1 000 tokens (as of 2025-Q1).
# Sources: AWS Bedrock pricing page.
MODEL_PRICING: dict[str, ModelPricingEntry] = {
    # Claude Sonnet 4.6
    "us.anthropic.claude-sonnet-4-6": ModelPricingEntry(
        input_price_per_1k=0.003,
        output_price_per_1k=0.015,
    ),
    # Claude Sonnet 3.7
    "us.anthropic.claude-3-7-sonnet-20250219-v1:0": ModelPricingEntry(
        input_price_per_1k=0.003,
        output_price_per_1k=0.015,
    ),
    # Claude Sonnet 3.5
    "anthropic.claude-3-5-sonnet-20241022-v2:0": ModelPricingEntry(
        input_price_per_1k=0.003,
        output_price_per_1k=0.015,
    ),
    # Claude Haiku 3.5
    "anthropic.claude-3-5-haiku-20241022-v1:0": ModelPricingEntry(
        input_price_per_1k=0.0008,
        output_price_per_1k=0.004,
    ),
    # Claude Haiku 3
    "anthropic.claude-3-haiku-20240307-v1:0": ModelPricingEntry(
        input_price_per_1k=0.00025,
        output_price_per_1k=0.00125,
    ),
    # Claude Opus 3
    "anthropic.claude-3-opus-20240229-v1:0": ModelPricingEntry(
        input_price_per_1k=0.015,
        output_price_per_1k=0.075,
    ),
}

_DEFAULT_PRICING = ModelPricingEntry(input_price_per_1k=0.0, output_price_per_1k=0.0)


def get_pricing(model_id: str) -> ModelPricingEntry:
    """Return the pricing entry for *model_id*, or a zero-cost default."""
    # Exact match first
    if model_id in MODEL_PRICING:
        return MODEL_PRICING[model_id]
    # Substring match — handles cross-region prefixes like "us." or "eu."
    for key, entry in MODEL_PRICING.items():
        if key in model_id or model_id in key:
            return entry
    return _DEFAULT_PRICING


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TokenUsage:
    """Raw token counts returned by a single model invocation."""

    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class CallRecord:
    """Record of a single Bedrock invocation — tokens consumed and cost."""

    model_id: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

@dataclass
class TokenTracker:
    """Tracks token usage and estimated cost across Bedrock API calls.

    Designed to be injected into :class:`AWSBedrockProvider` so that callers
    can inspect cumulative totals after a processing run.

    Example::

        tracker = TokenTracker()
        provider = AWSBedrockProvider(config, token_tracker=tracker)
        ...
        print(tracker.summary())
    """

    _calls: list[CallRecord] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------
    # Public mutation
    # ------------------------------------------------------------------

    def record(self, *, model_id: str, input_tokens: int, output_tokens: int) -> None:
        """Record a single API call and log the usage.

        Args:
            model_id: The Bedrock model identifier used for this call.
            input_tokens: Number of input (prompt) tokens consumed.
            output_tokens: Number of output (completion) tokens generated.
        """
        pricing = get_pricing(model_id)
        cost = (
            input_tokens / 1000.0 * pricing.input_price_per_1k
            + output_tokens / 1000.0 * pricing.output_price_per_1k
        )
        call_record = CallRecord(
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
        )
        self._calls.append(call_record)

        logger.info(
            "bedrock_token_usage",
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=round(cost, 6),
            cumulative_total_tokens=self.cumulative_total_tokens,
            cumulative_cost_usd=round(self.cumulative_cost_usd, 6),
        )

    def reset(self) -> None:
        """Clear all recorded calls and reset cumulative totals."""
        self._calls.clear()

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def calls(self) -> list[CallRecord]:
        return list(self._calls)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def cumulative_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self._calls)

    @property
    def cumulative_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self._calls)

    @property
    def cumulative_total_tokens(self) -> int:
        return sum(c.total_tokens for c in self._calls)

    @property
    def cumulative_cost_usd(self) -> float:
        return sum(c.estimated_cost_usd for c in self._calls)

    # ------------------------------------------------------------------
    # Human-readable summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable summary of all token usage and costs."""
        lines = [
            "=== Token Usage Summary ===",
            f"  Calls        : {self.call_count}",
            f"  Input tokens : {self.cumulative_input_tokens:,}",
            f"  Output tokens: {self.cumulative_output_tokens:,}",
            f"  Total tokens : {self.cumulative_total_tokens:,}",
            f"  Est. cost    : ${self.cumulative_cost_usd:.6f} USD",
        ]
        return "\n".join(lines)

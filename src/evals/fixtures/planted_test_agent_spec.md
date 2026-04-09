# Test Agent Eval — behaviour to test

**Source file**: `src/domain/eval_test_agent_target.py`

**Behaviour**:

A function `clamp(value: int, low: int, high: int) -> int` that:
1. Returns `value` unchanged if `low <= value <= high`.
2. Returns `low` if `value < low`.
3. Returns `high` if `value > high`.
4. Raises `ValueError` if `low > high`.

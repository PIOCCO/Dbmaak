import pytest

from security.guards import CallToolGuard


def test_tool_rate_limit() -> None:
    guard = CallToolGuard(max_calls_per_tool=2, min_interval_seconds=0)
    guard.check_and_record("get_business_info")
    guard.check_and_record("get_business_info")
    with pytest.raises(RuntimeError):
        guard.check_and_record("get_business_info")

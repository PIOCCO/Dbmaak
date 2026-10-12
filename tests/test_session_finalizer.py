from agent.session_lifecycle import CallSessionFinalizer
from observability.metrics import get_metrics


def test_finalize_runs_once():
    get_metrics().reset()
    calls: list[str] = []

    finalizer = CallSessionFinalizer(
        call_id="c1",
        business_id="demo_salon",
        on_finalize=lambda status: calls.append(status),
    )
    finalizer.finalize("completed")
    finalizer.finalize("failed")
    assert calls == ["completed"]
    snap = get_metrics().snapshot()
    assert snap.counters.get("session_ended|business_id=demo_salon", 0) == 1

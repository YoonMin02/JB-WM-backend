"""Route surface tests for legacy compatibility and redesigned workflows."""

from __future__ import annotations


def test_fastapi_registers_legacy_and_redesign_routes():
    from app.main import app

    routes = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes}
    paths = {path for path, _ in routes}

    assert "/customers" in paths
    assert "/customers/{customer_id}/agent-sessions" in paths
    assert "/agent-sessions/{session_id}" in paths
    assert "/agent-sessions/{session_id}/proposals" in paths
    assert "/customers/{customer_id}/workflow-sessions" in paths
    assert "/workflow-sessions/{thread_id}" in paths
    assert "/workflow-sessions/{thread_id}/debug" in paths
    assert "/workflow-sessions/{thread_id}/events" in paths
    assert "/workflow-sessions/{thread_id}/decisions" in paths

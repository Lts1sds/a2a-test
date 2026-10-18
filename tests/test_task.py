"""Task lifecycle smoke tests against the live compliant fixture server."""

from __future__ import annotations

from a2a_test.checks import CheckSuite, Status
from a2a_test.client import A2AClient
from a2a_test.task import smoke_task


def _run(base_url: str, capabilities=None) -> CheckSuite:
    suite = CheckSuite()
    smoke_task(suite, A2AClient(base_url), capabilities=capabilities or {})
    return suite


def _by_name(suite: CheckSuite, name: str):
    for r in suite.results:
        if r.name == name:
            return r
    return None


def test_task_lifecycle_happy_path(good_server):
    suite = _run(good_server, capabilities={"streaming": False})
    for name in (
        "send-message",
        "task:id",
        "task:initial-state",
        "task:context-id",
        "lifecycle:terminal",
        "lifecycle:cancel-terminal",
        "lifecycle:message-terminal",
    ):
        r = _by_name(suite, name)
        assert r is not None, name
        assert r.status == Status.PASS, f"{name}: {r.detail}"
    r = _by_name(suite, "lifecycle:terminal")
    assert "TASK_STATE_COMPLETED" in r.detail


def test_streaming_declared_and_valid(good_server):
    suite = _run(good_server, capabilities={"streaming": True})
    for name in (
        "streaming:frames",
        "streaming:first-event",
        "streaming:discriminator",
        "streaming:terminal-close",
    ):
        r = _by_name(suite, name)
        assert r is not None, name
        assert r.status == Status.PASS, f"{name}: {r.detail}"


def test_streaming_skipped_when_not_declared(good_server):
    suite = _run(good_server, capabilities={"streaming": False})
    r = _by_name(suite, "streaming")
    assert r is not None and r.status == Status.SKIP


def test_legacy_part_discriminator_flagged(bad_server):
    # bad server answers message/send (v0.3) with `kind` parts; but our tool
    # speaks PascalCase SendMessage, which the bad server rejects -> send fails.
    # So instead exercise the discriminator check through a direct message result.
    suite = CheckSuite()
    from a2a_test.task import _check_message_shape

    _check_message_shape(
        suite,
        "task",
        {
            "messageId": "m-1",
            "role": "ROLE_AGENT",
            "parts": [{"kind": "text", "text": "hi"}],
        },
    )
    r = _by_name(suite, "message:part-discriminator")
    assert r is not None and r.status == Status.FAIL
    r = _by_name(suite, "message:messageId")
    assert r is not None and r.status == Status.PASS

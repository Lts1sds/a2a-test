"""JSON-RPC conformance probes against live fixture servers."""

from __future__ import annotations

from a2a_test.checks import CheckSuite, Status
from a2a_test.client import A2AClient
from a2a_test.probe import probe_protocol


def _run(base_url: str) -> CheckSuite:
    suite = CheckSuite()
    probe_protocol(suite, A2AClient(base_url))
    return suite


def _by_name(suite: CheckSuite, name: str):
    for r in suite.results:
        if r.name == name:
            return r
    return None


def test_good_server_error_matrix(good_server):
    suite = _run(good_server)
    for name in (
        "error:task-not-found",
        "error:cancel-not-found",
        "error:method-not-found",
        "error:parse-error",
        "error:invalid-request",
        "error:invalid-params",
    ):
        r = _by_name(suite, name)
        assert r is not None, name
        assert r.status == Status.PASS, f"{name}: {r.detail}"


def test_good_server_method_style(good_server):
    suite = _run(good_server)
    r = _by_name(suite, "method-style")
    assert r is not None and r.status == Status.PASS, r.detail if r else ""


def test_good_server_version_negotiation(good_server):
    suite = _run(good_server)
    for name in ("version:negotiation", "version:empty-header"):
        r = _by_name(suite, name)
        assert r is not None and r.status == Status.PASS, f"{name}: {r.detail}"


def test_legacy_server_method_style_flagged(bad_server):
    suite = _run(bad_server)
    r = _by_name(suite, "method-style")
    assert r is not None and r.status == Status.FAIL
    assert "pre-1.0 dialect" in r.detail


def test_legacy_server_wrong_error_code_flagged(bad_server):
    suite = _run(bad_server)
    r = _by_name(suite, "error:task-not-found")
    # PascalCase GetTask is unknown to the legacy server -> -32601 instead of -32001
    assert r is not None and r.status != Status.PASS
    assert "-32601" in r.detail or "-32603" in r.detail

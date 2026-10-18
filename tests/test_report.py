"""Report rendering and exit-code semantics."""

from __future__ import annotations

import io
import json

from a2a_test.checks import CheckResult, CheckSuite, Status
from a2a_test.report import render, render_json, render_tap


def _demo_suite() -> CheckSuite:
    s = CheckSuite()
    s.add(CheckResult("g1", "ok-check", Status.PASS, "fine"))
    s.add(CheckResult("g1", "bad-check", Status.FAIL, "expected -32001, got -32603"))
    s.add(CheckResult("g2", "warn-check", Status.WARN, "custom binding"))
    s.add(CheckResult("g2", "skip-check", Status.SKIP, "not declared"))
    s.add(CheckResult("g2", "info-check", Status.INFO, "streaming supported"))
    return s


def test_exit_code_semantics():
    s = _demo_suite()
    assert s.failed == 1
    assert s.exit_code == 1
    s2 = CheckSuite()
    s2.add(CheckResult("g", "w", Status.WARN))
    assert s2.exit_code == 0  # WARN must not fail CI


def test_tap_output():
    out = io.StringIO()
    render_tap(_demo_suite(), out)
    lines = out.getvalue().splitlines()
    assert lines[0] == "1..5"
    assert "ok 1 - g1 / ok-check" in lines
    assert "not ok 2 - g1 / bad-check" in lines
    assert "ok 3 - g2 / warn-check # TODO warning" in lines
    assert "ok 4 - g2 / skip-check # SKIP" in lines
    assert "ok 5 - g2 / info-check # NOTE info" in lines
    assert any("expected -32001" in ln for ln in lines)


def test_json_output():
    out = io.StringIO()
    render_json(_demo_suite(), out)
    data = json.loads(out.getvalue())
    assert data["summary"]["total"] == 5
    assert data["summary"]["failed"] == 1
    assert data["summary"]["exit_code"] == 1
    assert data["results"][1]["status"] == "FAIL"


def test_render_dispatch():
    out = io.StringIO()
    render(_demo_suite(), "tap", out)
    assert out.getvalue().startswith("1..5")
    out2 = io.StringIO()
    render(_demo_suite(), "json", out2)
    assert "summary" in out2.getvalue()
    out3 = io.StringIO()
    render(_demo_suite(), "human", out3)
    assert "[g1]" in out3.getvalue()

"""Agent Card checks against live fixture servers."""

from __future__ import annotations

from a2a_test.card import check_agent_card, fetch_agent_card
from a2a_test.checks import CheckSuite, Status
from a2a_test.client import A2AClient


def _run(base_url: str) -> CheckSuite:
    suite = CheckSuite()
    check_agent_card(suite, A2AClient(base_url))
    return suite


def _by_name(suite: CheckSuite, name: str):
    for r in suite.results:
        if r.name == name:
            return r
    return None


def test_good_card_all_pass(good_server):
    suite = _run(good_server)
    fails = [r for r in suite.results if r.status == Status.FAIL]
    assert not fails, [f"{r.name}: {r.detail}" for r in fails]
    assert suite.exit_code == 0


def test_good_card_required_fields(good_server):
    suite = _run(good_server)
    for field in (
        "name",
        "supportedInterfaces",
        "version",
        "capabilities",
        "defaultInputModes",
        "defaultOutputModes",
        "skills",
    ):
        r = _by_name(suite, f"field:{field}")
        assert r is not None and r.status == Status.PASS, field


def test_good_card_no_legacy_fields(good_server):
    suite = _run(good_server)
    for legacy in ("preferredTransport", "supportsExtendedAgentCard", "url", "security"):
        r = _by_name(suite, f"legacy-field:{legacy}")
        assert r is not None and r.status == Status.PASS, legacy


def test_good_card_skill_ids_unique(good_server):
    suite = _run(good_server)
    r = _by_name(suite, "skill-ids-unique")
    assert r is not None and r.status == Status.PASS


def test_legacy_card_reports_v03_fields(bad_server):
    suite = _run(bad_server)
    for legacy in ("preferredTransport", "supportsExtendedAgentCard", "url"):
        r = _by_name(suite, f"legacy-field:{legacy}")
        assert r is not None and r.status == Status.FAIL, f"{legacy} should be flagged"
    assert suite.exit_code == 1


def test_fetch_card_missing_server():
    # nothing listens on this port; fetch must fail gracefully
    client = A2AClient("http://127.0.0.1:1")
    card, err = fetch_agent_card(client)
    assert card is None
    assert err

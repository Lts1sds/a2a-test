"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .card import check_agent_card
from .checks import CheckSuite
from .client import DEFAULT_TIMEOUT, A2AClient
from .probe import probe_protocol
from .report import render
from .rest import discover_rest_interface, probe_rest
from .task import smoke_task

EPILOG = """\
examples:
  a2a-test all http://localhost:9999
  a2a-test card https://agent.example.com
  a2a-test probe http://localhost:9999 --format tap
  a2a-test rest http://localhost:9999
  a2a-test all https://agent.example.com --format json > report.json

exit code is 1 when any check FAILs (WARN does not fail), so it can gate CI.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="a2a-test",
        description="Compliance test suite for A2A (Agent2Agent) protocol servers.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"a2a-test {__version__}")
    sub = parser.add_subparsers(dest="command")

    def add_target(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "target", metavar="URL", help="A2A server base URL, e.g. http://localhost:9999"
        )
        p.add_argument(
            "--timeout",
            type=float,
            default=DEFAULT_TIMEOUT,
            help=f"per-request timeout in seconds (default {DEFAULT_TIMEOUT})",
        )
        p.add_argument(
            "--format",
            choices=["human", "tap", "json"],
            default="human",
            help="output format (default human)",
        )
        p.add_argument(
            "--message",
            default="Reply with the single word: pong",
            help="text sent in the task smoke test",
        )
        p.add_argument(
            "--task-timeout",
            type=float,
            default=60.0,
            help="seconds to wait for a task to reach a terminal state (default 60)",
        )

    for name, help_text in [
        ("card", "fetch and validate the Agent Card (structure + v0.3 legacy fields)"),
        ("probe", "JSON-RPC conformance: error codes, method style, version negotiation"),
        ("task", "task lifecycle smoke test (send, poll, terminal, guards, streaming)"),
        ("rest", "REST (HTTP+JSON) binding conformance: paths, error format, pagination"),
        ("all", "run every suite: card + probe + task + rest"),
    ]:
        p = sub.add_parser(name, help=help_text)
        add_target(p)
    return parser


def _fetch_card(client: A2AClient) -> dict | None:
    """Fetch and parse the Agent Card without running card checks."""
    try:
        _status, _ctype, body = client.fetch_card()
        card = json.loads(body)
        if isinstance(card, dict):
            return card
    except (ValueError, OSError):
        pass
    return None


def run_suites(args: argparse.Namespace, client: A2AClient) -> CheckSuite:
    suite = CheckSuite()
    command = getattr(args, "command", None) or "all"
    card = None
    if command in ("card", "all"):
        card = check_agent_card(suite, client)
    if command in ("probe", "all"):
        probe_protocol(suite, client)
    if command in ("task", "all"):
        caps = {}
        if isinstance(card, dict) and isinstance(card.get("capabilities"), dict):
            caps = card["capabilities"]
        smoke_task(
            suite,
            client,
            message_text=getattr(args, "message", None) or "pong",
            capabilities=caps,
            task_timeout=getattr(args, "task_timeout", 60.0),
        )
    if command in ("rest", "all"):
        if card is None:
            card = _fetch_card(client)
        rest_base = discover_rest_interface(card)
        if rest_base:
            caps = {}
            if isinstance(card, dict) and isinstance(card.get("capabilities"), dict):
                caps = card["capabilities"]
            probe_rest(suite, client, rest_base, capabilities=caps)
        else:
            suite.skip(
                "rest",
                "interface",
                "no HTTP+JSON interface declared in the Agent Card "
                "(supportedInterfaces[].protocolBinding == 'HTTP+JSON')",
            )
    return suite


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)
    if not command:
        parser.print_help()
        return 2
    client = A2AClient(args.target, timeout=getattr(args, "timeout", DEFAULT_TIMEOUT))
    try:
        suite = run_suites(args, client)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    render(suite, getattr(args, "format", "human"))
    return suite.exit_code


if __name__ == "__main__":
    sys.exit(main())

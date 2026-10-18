"""Output renderers: human (ANSI color), TAP 14, and JSON."""

from __future__ import annotations

import json
import sys
from typing import TextIO

from .checks import CheckSuite, Status

_ANSI = sys.stdout.isatty() if hasattr(sys, "stdout") and sys.stdout else False
_COLOR = {
    Status.PASS: "\033[32m",  # green
    Status.FAIL: "\033[31m",  # red
    Status.WARN: "\033[33m",  # yellow
    Status.SKIP: "\033[90m",  # gray
    Status.INFO: "\033[36m",  # cyan
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_SYMBOL = {
    Status.PASS: "PASS",
    Status.FAIL: "FAIL",
    Status.WARN: "WARN",
    Status.SKIP: "skip",
    Status.INFO: "info",
}


def render_human(suite: CheckSuite, out: TextIO = sys.stdout) -> None:
    for group in suite.groups():
        out.write(f"\n{_BOLD}[{group}]{_RESET}\n")
        for r in suite.by_group(group):
            color = _COLOR.get(r.status, "") if _ANSI else ""
            sym = _SYMBOL.get(r.status, r.status.value)
            line = f"  {color}{sym.ljust(4)}{_RESET if _ANSI else ''} {r.name}"
            if r.detail:
                line += f" - {r.detail}"
            out.write(line + "\n")
    out.write("\n")
    summary = (
        f"{suite.passed} passed, {suite.failed} failed, "
        f"{suite.warned} warned, {suite.skipped} skipped"
    )
    if _ANSI:
        color = "\033[31m" if suite.failed else "\033[32m"
        out.write(f"{_BOLD}{color}{summary}{_RESET}\n")
    else:
        out.write(f"{summary}\n")


def render_tap(suite: CheckSuite, out: TextIO = sys.stdout) -> None:
    """TAP 14 output, consumable by any CI test reporter."""
    out.write(f"1..{len(suite.results)}\n")
    for i, r in enumerate(suite.results, 1):
        if r.status == Status.PASS:
            directive = ""
        elif r.status == Status.WARN:
            directive = " # TODO warning"
        elif r.status == Status.SKIP:
            directive = " # SKIP"
        elif r.status == Status.INFO:
            directive = " # NOTE info"
        else:
            directive = ""
        ok = "ok" if r.status in (Status.PASS, Status.WARN, Status.SKIP, Status.INFO) else "not ok"
        line = f"{ok} {i} - {r.group} / {r.name}{directive}"
        if r.detail and r.status == Status.FAIL:
            escaped = r.detail.replace("\\", "\\\\").replace("\n", "\\n")
            line += f'\n  ---\n  message: "{escaped}"\n  ---'
        out.write(line + "\n")


def render_json(suite: CheckSuite, out: TextIO = sys.stdout) -> None:
    json.dump(suite.to_dict(), out, indent=2)
    out.write("\n")


def render(suite: CheckSuite, fmt: str, out: TextIO = sys.stdout) -> None:
    if fmt == "tap":
        render_tap(suite, out)
    elif fmt == "json":
        render_json(suite, out)
    else:
        render_human(suite, out)

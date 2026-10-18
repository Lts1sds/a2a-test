"""Check result model and collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    INFO = "INFO"


@dataclass
class CheckResult:
    """A single named check outcome."""

    group: str
    name: str
    status: Status
    detail: str = ""
    data: dict[str, Any] | None = None


@dataclass
class CheckSuite:
    """Accumulates CheckResults and computes summary + exit code."""

    results: list[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    def check(self, group: str, name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        """Add a boolean check. Fails (or warns) when ``ok`` is false."""
        if ok:
            self.add(CheckResult(group, name, Status.PASS, detail))
        else:
            self.add(CheckResult(group, name, Status.WARN if warn else Status.FAIL, detail))

    def info(self, group: str, name: str, detail: str = "") -> None:
        self.add(CheckResult(group, name, Status.INFO, detail))

    def skip(self, group: str, name: str, detail: str = "") -> None:
        self.add(CheckResult(group, name, Status.SKIP, detail))

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == Status.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == Status.FAIL)

    @property
    def warned(self) -> int:
        return sum(1 for r in self.results if r.status == Status.WARN)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == Status.SKIP)

    @property
    def exit_code(self) -> int:
        """0 when no FAIL results, 1 otherwise. WARN does not fail CI."""
        return 1 if self.failed else 0

    def groups(self) -> list[str]:
        seen: list[str] = []
        for r in self.results:
            if r.group not in seen:
                seen.append(r.group)
        return seen

    def by_group(self, group: str) -> list[CheckResult]:
        return [r for r in self.results if r.group == group]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total": len(self.results),
                "passed": self.passed,
                "failed": self.failed,
                "warned": self.warned,
                "skipped": self.skipped,
                "exit_code": self.exit_code,
            },
            "results": [
                {
                    "group": r.group,
                    "name": r.name,
                    "status": r.status.value,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }

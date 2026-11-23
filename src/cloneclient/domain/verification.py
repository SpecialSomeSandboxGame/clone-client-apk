"""Pure verification result models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class VerificationReport:
    checks: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    @property
    def failed(self) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def to_lines(self) -> list[str]:
        mark = "PASS" if self.passed else "FAIL"
        lines = [f"verification: {mark}"]
        for check in self.checks:
            status = "ok" if check.passed else "failed"
            lines.append(f"[{status}] {check.name}: {check.detail}")
        return lines

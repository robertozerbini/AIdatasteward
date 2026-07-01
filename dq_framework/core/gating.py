"""Severity-driven verdict logic — pure, no Spark.

A check result is a mapping with:
  - status:   "pass" | "fail"
  - severity: "error" | "warn"

`passed` is True when no check failed.
`gated`  is True when at least one *error*-severity check failed; downstream
work must not proceed. Warn-level failures are recorded/alerted but never gate.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    passed: bool
    gated: bool


def decide(results) -> Verdict:
    failures = [r for r in results if r["status"] == "fail"]
    passed = len(failures) == 0
    gated = any(r["severity"] == "error" for r in failures)
    return Verdict(passed=passed, gated=gated)

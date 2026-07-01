"""CLI entry point for job tasks: `dq-run --config <path> --trigger <trigger>`.

Dispatches to the right facade function based on the config's `kind`, prints a
one-line summary, and exits non-zero (via raise_if_gated) when an error-severity
check fails so the Databricks task is marked failed. Runtime-only.
"""
import argparse

from dq_framework.core.config import validate_config
from dq_framework import facade

# Load the YAML once here to route by kind, reusing the facade's loader.
_DISPATCH = {
    "rowlevel": facade.run_row_checks,
    "endpoint": facade.run_endpoint_checks,
    "kpi": facade.run_kpi_asserts,
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="dq-run")
    parser.add_argument("--config", required=True, help="Path to a YAML check config")
    parser.add_argument("--trigger", default="schedule",
                        choices=["pipeline", "schedule", "ondemand"])
    parser.add_argument("--notify", default=None,
                        help="Path to a notifications YAML (channels + routes)")
    parser.add_argument("--no-gate", action="store_true",
                        help="Record results but do not fail the task on error checks")
    args = parser.parse_args()

    cfg = facade._load_config(args.config)  # validated Config
    validate_config(cfg.raw)                # explicit fail-fast on bad config

    result = _DISPATCH[cfg.kind](config=cfg, trigger=args.trigger, notify=args.notify)

    failed = [r["check_name"] for r in result.results if r["status"] == "fail"]
    print(f"[dq-run] target={cfg.target} kind={cfg.kind} "
          f"passed={result.passed} gated={result.gated} "
          f"checks={len(result.results)} failed={failed}")

    if not args.no_gate:
        result.raise_if_gated()


if __name__ == "__main__":
    main()

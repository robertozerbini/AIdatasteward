"""Public entry points, called from pipeline notebooks and job tasks.

    from dq_framework import run_row_checks, run_endpoint_checks, run_kpi_asserts

All three run the shared engine, write to the same results table, and return a
DQResult carrying the severity-driven verdict. Runtime-only (pyspark/DQX).
"""
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Union

import yaml

from dq_framework.core.config import validate_config, Config
from dq_framework.core.gating import decide
from dq_framework.spark import store, rowlevel, endpoint, kpi
from dq_framework.notify import dispatch

# Override per-config with a top-level `results_table:` key.
DEFAULT_RESULTS_TABLE = "prod_auto.gold_virtual.dq_results"


@dataclass
class DQResult:
    passed: bool
    gated: bool
    results: list = field(default_factory=list)  # list[dict] in common shape
    results_df: object = None
    valid_df: object = None       # row-level only
    quarantine_df: object = None  # row-level only

    def raise_if_gated(self):
        """Stop the pipeline/job if any error-severity check failed."""
        if self.gated:
            failed = [r["check_name"] for r in self.results
                      if r["status"] == "fail" and r["severity"] == "error"]
            raise DataQualityGateError(f"DQ gate failed on error checks: {failed}")
        return self


class DataQualityGateError(Exception):
    """Raised by DQResult.raise_if_gated when an error-severity check failed."""


def _load_config(config: Union[str, dict, Config]) -> Config:
    if isinstance(config, Config):
        return config
    if isinstance(config, dict):
        return validate_config(config)
    # str: a YAML file path, else treat the string itself as YAML.
    if os.path.exists(config):
        with open(config) as fh:
            parsed = yaml.safe_load(fh)
    else:
        parsed = yaml.safe_load(config)
    return validate_config(parsed)


def _ctx(trigger: str) -> dict:
    return {"run_id": str(uuid.uuid4()),
            "run_ts": datetime.now(timezone.utc),
            "trigger": trigger}


def _load_mapping(x) -> dict:
    """Load a notify config from a dict, a YAML file path, or a YAML string."""
    if isinstance(x, dict):
        return x
    if os.path.exists(x):
        with open(x) as fh:
            return yaml.safe_load(fh)
    return yaml.safe_load(x)


def _finish(spark, cfg: Config, rows: list, *, write: bool, notify=None,
            valid_df=None, quarantine_df=None) -> DQResult:
    verdict = decide(rows)
    results_df = None
    if write and rows:
        table = cfg.raw.get("results_table", DEFAULT_RESULTS_TABLE)
        results_df = store.write_results(spark, table, rows)

    # A `notifications:` block on the check config is the default source; an
    # explicit `notify=` argument overrides it.
    notify_config = notify if notify is not None else cfg.raw.get("notifications")
    if notify_config and any(r["status"] == "fail" for r in rows):
        dispatch(rows, _load_mapping(notify_config))

    return DQResult(
        passed=verdict.passed, gated=verdict.gated, results=rows,
        results_df=results_df, valid_df=valid_df, quarantine_df=quarantine_df,
    )


def run_row_checks(df=None, *, config, trigger="pipeline", spark=None,
                   write=True, notify=None) -> DQResult:
    spark = spark or store.get_spark()
    cfg = _load_config(config)
    valid_df, quarantine_df, rows = rowlevel.run(spark, cfg, df=df, **_ctx(trigger))
    return _finish(spark, cfg, rows, write=write, notify=notify,
                   valid_df=valid_df, quarantine_df=quarantine_df)


def run_endpoint_checks(*, config, trigger="schedule", spark=None,
                        write=True, notify=None) -> DQResult:
    spark = spark or store.get_spark()
    cfg = _load_config(config)
    rows = endpoint.run(spark, cfg, **_ctx(trigger))
    return _finish(spark, cfg, rows, write=write, notify=notify)


def run_kpi_asserts(*, config, trigger="schedule", spark=None,
                    write=True, notify=None) -> DQResult:
    spark = spark or store.get_spark()
    cfg = _load_config(config)
    rows = kpi.run(spark, cfg, **_ctx(trigger))
    return _finish(spark, cfg, rows, write=write, notify=notify)

"""Config validation — pure, no Spark.

Validates a parsed config mapping (from YAML) for one of the three check kinds
and returns a light typed handle. Kind-specific required keys are enforced so a
misconfigured rule fails fast at load time rather than mid-run.
"""
from dataclasses import dataclass
from typing import Any

VALID_KINDS = ("rowlevel", "endpoint", "kpi")

# Required keys beyond the common {kind, target}, per kind.
_REQUIRED_BY_KIND = {
    "rowlevel": ["checks"],
    "endpoint": ["execute", "result_checks"],
    "kpi": ["ground_truth_table", "kpis"],
}


class ConfigError(ValueError):
    """Raised when a config mapping is missing or has invalid required keys."""


@dataclass(frozen=True)
class Config:
    kind: str
    target: str
    raw: dict


def _require(cfg: dict, key: str) -> Any:
    if key not in cfg or cfg[key] in (None, "", [], {}):
        raise ConfigError(f"config missing required key: '{key}'")
    return cfg[key]


def validate_config(cfg: dict) -> Config:
    kind = _require(cfg, "kind")
    if kind not in VALID_KINDS:
        raise ConfigError(f"invalid 'kind': {kind!r} (expected one of {VALID_KINDS})")

    target = _require(cfg, "target")

    for key in _REQUIRED_BY_KIND[kind]:
        _require(cfg, key)

    return Config(kind=kind, target=target, raw=cfg)

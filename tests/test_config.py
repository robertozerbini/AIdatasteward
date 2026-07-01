import pytest

from dq_framework.core.config import validate_config, ConfigError


def _rowlevel():
    return {
        "kind": "rowlevel",
        "target": "prod.gold.orgstrc",
        "checks": [
            {"name": "org_key_unique", "criticality": "error",
             "check": {"function": "is_unique", "arguments": {"columns": ["org_key"]}}},
        ],
    }


def _endpoint():
    return {
        "kind": "endpoint",
        "target": "sp_customer_360",
        "execute": "CALL prod.gold.sp_customer_360()",
        "result_checks": [{"name": "non_empty", "severity": "error", "assert": "row_count > 0"}],
    }


def _kpi():
    return {
        "kind": "kpi",
        "target": "revenue_kpis",
        "ground_truth_table": "prod.gold.dq_kpi_ground_truth",
        "kpis": [{"name": "total_revenue", "query": "SELECT sum(amount) FROM prod.gold.sales"}],
    }


def test_valid_rowlevel_returns_kind_and_target():
    cfg = validate_config(_rowlevel())
    assert cfg.kind == "rowlevel"
    assert cfg.target == "prod.gold.orgstrc"


def test_valid_endpoint_and_kpi_parse():
    assert validate_config(_endpoint()).kind == "endpoint"
    assert validate_config(_kpi()).kind == "kpi"


def test_missing_kind_raises():
    cfg = _rowlevel()
    del cfg["kind"]
    with pytest.raises(ConfigError, match="kind"):
        validate_config(cfg)


def test_unknown_kind_raises():
    cfg = _rowlevel()
    cfg["kind"] = "bogus"
    with pytest.raises(ConfigError, match="kind"):
        validate_config(cfg)


def test_missing_target_raises():
    cfg = _rowlevel()
    del cfg["target"]
    with pytest.raises(ConfigError, match="target"):
        validate_config(cfg)


def test_rowlevel_without_checks_raises():
    cfg = _rowlevel()
    cfg["checks"] = []
    with pytest.raises(ConfigError, match="checks"):
        validate_config(cfg)


def test_endpoint_without_execute_raises():
    cfg = _endpoint()
    del cfg["execute"]
    with pytest.raises(ConfigError, match="execute"):
        validate_config(cfg)


def test_kpi_without_ground_truth_table_raises():
    cfg = _kpi()
    del cfg["ground_truth_table"]
    with pytest.raises(ConfigError, match="ground_truth_table"):
        validate_config(cfg)


def test_config_exposes_raw_dict():
    raw = _rowlevel()
    cfg = validate_config(raw)
    assert cfg.raw is raw

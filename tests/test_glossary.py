"""Guards for the Funnel 2.0 business glossary.

Keeps the generated markdown in lock-step with glossary.yaml (the source of
truth) and asserts the six headline funnel KPIs are always present, so the
glossary cannot silently drift or lose a KPI.
"""
import importlib.util
from pathlib import Path

import pytest
import yaml

GLOSSARY_DIR = Path(__file__).resolve().parent.parent / "glossary" / "funnel_2_0"
SOURCE = GLOSSARY_DIR / "glossary.yaml"

FUNNEL_KPIS = [
    "Leads",
    "Hot Leads",
    "Visits",
    "Test Drives",
    "Total Reservations",
    "Invoices",
    "Total Open Reservations (Reservation Bank)",
]


def _load_renderer():
    spec = importlib.util.spec_from_file_location(
        "render_glossary", GLOSSARY_DIR / "render_glossary.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_funnel_kpis_present():
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    names = [k["name"] for k in data["kpis"]]
    assert names == FUNNEL_KPIS  # exact set, in journey order


def test_every_kpi_is_fully_defined():
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    for kpi in data["kpis"]:
        for field in ("definition", "pseudo_code", "source_system", "technical"):
            assert kpi.get(field) is not None, f"{kpi.get('name')!r} is missing {field!r}"
            if field != "technical":
                assert str(kpi[field]).strip(), f"{kpi.get('name')!r} has empty {field!r}"
        # Implemented KPIs must carry their serving measure columns; a
        # not-yet-implemented KPI legitimately has none yet.
        if kpi.get("implemented", True):
            assert kpi["technical"].get("measure_columns"), kpi["name"]


def test_funnel_group_mapping_is_consistent():
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    fg = data["funnel_groups"]
    defined = {g["name"] for g in fg["groups"]}
    assert fg["mapping"], "funnel-group mapping is empty"
    # Every mapped GROUP is either a defined group or null (unmapped).
    for row in fg["mapping"]:
        assert row.get("group") is None or row["group"] in defined, row
    # Every key funnel KPI has a group-identification rule.
    ruled = {r["kpi"] for r in fg["per_kpi"]}
    for kpi in data["kpis"]:
        assert kpi["name"] in ruled, f"no funnel-group rule for {kpi['name']!r}"


@pytest.mark.parametrize("name", ["kpis.md", "terms.md", "funnel_groups.md"])
def test_generated_markdown_is_in_sync(name):
    renderer = _load_renderer()
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    rendered = renderer.TARGETS[name](data).rstrip() + "\n"
    on_disk = (GLOSSARY_DIR / name).read_text(encoding="utf-8")
    assert on_disk == rendered, (
        f"{name} is stale — run: python glossary/funnel_2_0/render_glossary.py"
    )

#!/usr/bin/env python3
"""Render the Funnel 2.0 business glossary markdown from glossary.yaml.

glossary.yaml is the single source of truth. This script regenerates the
human-readable companion files (kpis.md, terms.md) so the business glossary
and the machine-readable definitions never drift.

Usage
-----
    python glossary/funnel_2_0/render_glossary.py            # write kpis.md + terms.md
    python glossary/funnel_2_0/render_glossary.py --check    # fail if out of date (CI)

The `--check` mode regenerates in memory and diffs against the files on disk,
exiting non-zero if they differ — so a stale checkout is caught in review.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "glossary.yaml"
GENERATED_BANNER = (
    "<!-- GENERATED FILE — do not edit by hand.\n"
    "     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->\n"
)


def _clean(text: str) -> str:
    """Collapse the folded-scalar line breaks YAML leaves in long strings."""
    return " ".join((text or "").split())


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _code_join(values) -> str:
    items = _as_list(values)
    return ", ".join(f"`{v}`" for v in items) if items else "—"


def _cell(text: str) -> str:
    """Make a string safe for a markdown table cell (escape pipes, one line)."""
    return _clean(text).replace("|", "\\|") or "—"


_STATUS_LABELS = {
    "approved": "Approved",
    "under_approval": "Under approval",
    "proposed": "Proposed — for discussion",
    "draft": "Draft",
    "deprecated": "Deprecated",
}


def _status_label(kpi: dict) -> str:
    """Human-readable approval + implementation state for a KPI."""
    status = kpi.get("status", "under_approval")
    label = _STATUS_LABELS.get(status, status.replace("_", " ").capitalize())
    if kpi.get("implemented", True) is False:
        label += " · not yet implemented"
    return label


def render_kpis(data: dict) -> str:
    meta = data["meta"]
    kpis = sorted(data["kpis"], key=lambda k: k.get("stage", 0))

    out: list[str] = [GENERATED_BANNER]
    out.append(f"# {meta['funnel']} — KPI Business Glossary\n")
    out.append(f"_{meta['subtitle']}. Report table: `{meta['report_table']}`._\n")
    meta_status = _STATUS_LABELS.get(meta["status"], meta["status"])
    out.append(
        f"**Owner:** {meta['owner']} · **Status:** {meta_status} · "
        f"**Version:** {meta['version']} · **Last reviewed:** {meta['last_reviewed']}\n"
    )
    out.append(
        "> All definitions are **under approval** — pending steward validation, "
        "not yet signed off.\n"
    )
    out.append(
        "> Every KPI below can be split by **funnel group** (Digital / Walk-in / "
        "Others) — see [`funnel_groups.md`](funnel_groups.md).\n"
    )

    # Data dictionary — KPI | Status | Definition | Source | Pseudo code | Note.
    out.append("## Data dictionary\n")
    out.append("| KPI | Status | Definition | Source | Pseudo code | Note |")
    out.append("|-----|--------|------------|--------|-------------|------|")
    for k in kpis:
        out.append(
            f"| **{_cell(k['name'])}** "
            f"| {_cell(_status_label(k))} "
            f"| {_cell(k['definition'])} "
            f"| {_cell(k['source_system'])} "
            f"| {_cell(k['pseudo_code'])} "
            f"| {_cell(k.get('notes', ''))} |"
        )
    out.append("")

    # Lineage reference (kept separately so the dictionary stays readable).
    out.append("## Lineage reference\n")
    out.append("| KPI | Silver source | Gold product | Serving stream | Measure column(s) |")
    out.append("|-----|---------------|--------------|----------------|-------------------|")
    for k in kpis:
        tech = k["technical"]
        out.append(
            f"| **{_cell(k['name'])}** "
            f"| {_code_join(tech.get('silver_source'))} "
            f"| {_code_join(tech.get('gold_product'))} "
            f"| {_code_join(tech.get('serve_stream'))} "
            f"| {_code_join(tech.get('measure_columns'))} |"
        )
    out.append("")

    out.append("---\n")
    out.append(
        "See [`funnel_groups.md`](funnel_groups.md) for the Digital / Walk-in / "
        "Others channel split, [`terms.md`](terms.md) for the supporting business "
        "vocabulary, and [`../../docs/Funnel2.0.md`](../../docs/Funnel2.0.md) for "
        "full lineage.\n"
    )
    return "\n".join(out)


def render_terms(data: dict) -> str:
    meta = data["meta"]
    terms = sorted(data["terms"], key=lambda t: t["term"].lower())

    out: list[str] = [GENERATED_BANNER]
    out.append(f"# {meta['funnel']} — Business Terms\n")
    out.append(
        "Supporting vocabulary the KPI definitions rely on. "
        "See [`kpis.md`](kpis.md) for the KPIs themselves.\n"
    )
    for t in terms:
        related = ", ".join(f"_{r}_" for r in _as_list(t.get("related")))
        out.append(f"### {t['term']}\n")
        out.append(f"{_clean(t['definition'])}\n")
        if related:
            out.append(f"**Related:** {related}\n")
    return "\n".join(out)


def render_funnel_groups(data: dict) -> str:
    fg = data["funnel_groups"]
    meta = data["meta"]

    out: list[str] = [GENERATED_BANNER]
    out.append(f"# {meta['funnel']} — Funnel Groups (Digital / Walk-in / Others)\n")
    out.append(f"{_clean(fg['description'])}\n")

    # Group definitions.
    out.append("## Groups\n")
    for g in fg["groups"]:
        out.append(f"- **{_cell(g['name'])}** — {_clean(g['definition'])}")
    out.append("")

    # How the group is identified per KPI.
    out.append("## How the group is identified, per KPI\n")
    out.append("| KPI | How the funnel group is identified |")
    out.append("|-----|------------------------------------|")
    for row in fg["per_kpi"]:
        out.append(f"| **{_cell(row['kpi'])}** | {_cell(row['rule'])} |")
    out.append("")

    # Full lead_source + lead_type -> lead_group mapping.
    out.append("## Classification mapping (lead_source + lead_type → lead_group)\n")
    out.append(
        f"The authoritative lookup ({len(fg['mapping'])} rows), applied via "
        "`lead_type_mapping_new`. `null` = no source value.\n"
    )
    out.append("| lead_group | lead_type | lead_source |")
    out.append("|------------|-----------|-------------|")
    for m in fg["mapping"]:
        out.append(
            f"| {_cell(m.get('group'))} "
            f"| {_cell(m.get('type'))} "
            f"| {_cell(m.get('source')) if m.get('source') is not None else '`null`'} |"
        )
    out.append("")
    out.append("---\n")
    out.append("See [`kpis.md`](kpis.md) for the KPI definitions this dimension splits.\n")
    return "\n".join(out)


TARGETS = {
    "kpis.md": render_kpis,
    "terms.md": render_terms,
    "funnel_groups.md": render_funnel_groups,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the markdown is up to date without writing (exit 1 if stale).",
    )
    args = parser.parse_args()

    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))

    stale: list[str] = []
    for name, render in TARGETS.items():
        rendered = render(data).rstrip() + "\n"
        target = HERE / name
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if args.check:
            if current != rendered:
                stale.append(name)
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"wrote {target.relative_to(HERE.parent.parent)}")

    if args.check and stale:
        print(
            "Glossary markdown is out of date: "
            + ", ".join(stale)
            + "\nRun: python glossary/funnel_2_0/render_glossary.py",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

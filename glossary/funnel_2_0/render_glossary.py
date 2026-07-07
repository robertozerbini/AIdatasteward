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


def render_kpis(data: dict) -> str:
    meta = data["meta"]
    kpis = sorted(data["kpis"], key=lambda k: k.get("stage", 0))

    out: list[str] = [GENERATED_BANNER]
    out.append(f"# {meta['funnel']} — KPI Business Glossary\n")
    out.append(f"_{meta['subtitle']}. Report table: `{meta['report_table']}`._\n")
    out.append(
        f"**Owner:** {meta['owner']} · **Status:** {meta['status']} · "
        f"**Version:** {meta['version']} · **Last reviewed:** {meta['last_reviewed']}\n"
    )

    # Summary table.
    out.append("## Funnel at a glance\n")
    out.append("| # | KPI | Source | Serving stream | Measure column(s) |")
    out.append("|---|-----|--------|----------------|-------------------|")
    for k in kpis:
        measures = ", ".join(f"`{m}`" for m in _as_list(k["technical"].get("measure_columns")))
        out.append(
            f"| {k.get('stage', '')} | **{k['name']}** | {k['source_system']} "
            f"| `{k['technical'].get('serve_stream', '')}` | {measures} |"
        )
    out.append("")

    # Detail cards.
    out.append("## Definitions\n")
    for k in kpis:
        tech = k["technical"]
        out.append(f"### {k.get('stage', '')}. {k['name']}\n")
        domain = k.get("domain") or "—"
        out.append(
            f"- **Source system:** {k['source_system']}  \n"
            f"- **KPI domain:** {domain}  \n"
            f"- **Status:** {k.get('status', 'approved')}\n"
        )
        out.append(f"**Definition.** {_clean(k['definition'])}\n")
        out.append(f"**Calculation (pseudo-code).** {_clean(k['pseudo_code'])}\n")
        out.append("**Lineage.**\n")
        out.append(f"- Silver source: {_code_join(tech.get('silver_source'))}")
        out.append(f"- Gold product: {_code_join(tech.get('gold_product'))}")
        out.append(f"- Serving stream: {_code_join(tech.get('serve_stream'))}")
        out.append(f"- Measure column(s): {_code_join(tech.get('measure_columns'))}\n")
        if k.get("notes"):
            out.append(f"> **Notes.** {_clean(k['notes'])}\n")

    out.append("---\n")
    out.append(
        "See [`terms.md`](terms.md) for the supporting business vocabulary and "
        "[`../../docs/Funnel2.0.md`](../../docs/Funnel2.0.md) for full lineage.\n"
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


TARGETS = {
    "kpis.md": render_kpis,
    "terms.md": render_terms,
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

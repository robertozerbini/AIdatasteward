# Funnel 2.0 — Business Glossary

The authoritative, steward-owned business glossary for **Funnel 2.0**, the
lead-to-invoice automotive sales funnel served from `prsls_ldmg_actv_dy`.

It answers *"what does this KPI mean, how is it calculated, and where does it
come from?"* in one place, so business users, analysts and data stewards share
a single agreed definition.

## Contents

| File | What it is |
|------|-----------|
| **[`glossary.yaml`](glossary.yaml)** | **Single source of truth.** Machine-readable KPI + term definitions. Edit this. |
| [`kpis.md`](kpis.md) | Generated. The six funnel KPIs — definition, pseudo-code, lineage. |
| [`terms.md`](terms.md) | Generated. Supporting business vocabulary (LEAD_ID, walk-in, order type…). |
| [`render_glossary.py`](render_glossary.py) | Regenerates `kpis.md` and `terms.md` from `glossary.yaml`. |

## The KPIs

The funnel in journey order — **Leads → Hot Leads → Visits → Test Drives →
Total Reservations → Invoices**. See [`kpis.md`](kpis.md) for the full,
steward-approved definitions.

## How this glossary is maintained

`glossary.yaml` is the **only file you edit by hand.** `kpis.md` and `terms.md`
are generated from it and carry a "do not edit" banner — hand edits there are
overwritten on the next render.

To change a definition, add a KPI, or add a term:

1. Edit `glossary.yaml`.
2. Regenerate the markdown:
   ```bash
   python glossary/funnel_2_0/render_glossary.py
   ```
3. Bump `meta.version` / `meta.last_reviewed` in `glossary.yaml` for a material
   change, and commit `glossary.yaml` together with the regenerated markdown.

### Keeping it honest (CI)

`render_glossary.py --check` regenerates in memory and fails (exit 1) if the
committed markdown is stale — wire it into CI or a pre-commit hook so the
generated files can never drift from the source:

```bash
python glossary/funnel_2_0/render_glossary.py --check
```

## Source of record & alignment

- **Business definitions & pseudo-code** come from the steward-approved
  *"Key KPI Definitions — Sales Funnel 2.0"* workbook.
- **Technical lineage** (source systems, gold products, serving streams,
  measure columns) is kept in sync with:
  - [`../../docs/Funnel2.0.md`](../../docs/Funnel2.0.md) — definition & lineage
  - [`../../docs/FUNNEL_2_0_LINEAGE.md`](../../docs/FUNNEL_2_0_LINEAGE.md) — visual lineage

When the funnel logic in `docs/Funnel2.0.md` changes, review this glossary in the
same change so the business definitions and the technical lineage stay aligned.

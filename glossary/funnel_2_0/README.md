# Funnel 2.0 — Business Glossary

The authoritative, steward-owned business glossary for **Funnel 2.0**, the
lead-to-invoice automotive sales funnel served from `prsls_ldmg_actv_dy`.

It answers *"what does this KPI mean, how is it calculated, and where does it
come from?"* in one place, so business users, analysts and data stewards share
a single agreed definition.

> **Status: under approval.** All definitions here are pending steward
> validation — they are not yet signed off. Each row in [`kpis.md`](kpis.md)
> carries its own status, and metrics not yet built into the pipeline (e.g.
> the Reservation Bank) are flagged *not yet implemented*.

## Contents

| File | What it is |
|------|-----------|
| **[`glossary.yaml`](glossary.yaml)** | **Single source of truth.** Machine-readable KPI + term definitions. Edit this. |
| [`kpis.md`](kpis.md) | Generated. The funnel KPIs — status, definition, source, pseudo-code, note, measurement details (grain / time anchor / scope), lineage, and data-quality invariants. |
| [`funnel_groups.md`](funnel_groups.md) | Generated. The Digital / Walk-in / Others channel split, how each KPI is grouped, and the full SOURCE/TYPE → GROUP mapping. |
| [`terms.md`](terms.md) | Generated. Supporting business vocabulary (LEAD_ID, walk-in, order type…). |
| [`render_glossary.py`](render_glossary.py) | Regenerates `kpis.md`, `funnel_groups.md` and `terms.md` from `glossary.yaml`. |

## The KPIs

The funnel in journey order — **Leads → Hot Leads → Visits → Test Drives →
Total Reservations → Invoices** — plus **Total Open Reservations (Reservation
Bank)**, a stock/open-orders metric not yet implemented. See [`kpis.md`](kpis.md)
for the full definitions (all under approval).

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

### Open decisions

Tracked in the definitions (search the YAML / `kpis.md`):

- **`open_opportunities_14d` threshold** — column says `14d`, `docs/Funnel2.0.md`
  says "> 15 days". The build (`customer_enquiries_long`) is not in this repo;
  confirm 14 vs 15 days against that pipeline and update the Visits note.
- **Reservation counting basis** — current Total Reservations (line items) vs the
  proposed unique-orders KPI. Awaiting a steward decision (see the two adjacent
  KPI rows).

Resolved and recorded: walk-ins currently count in full toward Hot Leads
(intended, flagged as a simplification); the test-drive "open" column is the
misspelled `test_drives_oepn` (kept to match the physical schema).

### Funnel groups

The `lead_source` / `lead_type` → `lead_group` mapping in `funnel_groups.md` is
steward-confirmed and reproduced verbatim (order and casing preserved) in the
`funnel_groups.mapping` block of `glossary.yaml`. To add or reclassify a
channel, edit that block and re-render.

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

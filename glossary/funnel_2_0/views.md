<!-- GENERATED FILE — do not edit by hand.
     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->

# Funnel 2.0 — Report Views

The report shows the **same six KPIs** in every view — the views differ only in *which population* each counts. See [`kpis.md`](kpis.md) for the KPI definitions themselves.

| View | What it counts | Backing measures / flag |
|------|----------------|-------------------------|
| **Total** | The whole funnel — every KPI, all origins combined. | Base KPI columns (`leads`, `hot_leads`, `opportunities`, `test_drives_*`, `total_order_items`, `invoices`). |
| **Digital** | Digitally-originated leads and their downstream funnel. | Base KPI columns filtered to a digital-origin lead source. |
| **Walk-in** | Showroom visitors with no originating lead. | Walk-in portion (`leads` − `leads_without_walkins`); walk-in flag. |
| **Pop-up** | Activity at temporary pop-up outlets. | Base KPI columns filtered to pop-up sales offices. |
| **Web Attribution** | Events credited to a web / social origin. | `web_attributed_*` KPI columns. |

### Total

The unsegmented funnel: each KPI (Leads, Hot Leads, Visits, Test Drives, Total Reservations, Invoices) counted over all rows regardless of lead origin or channel. The other views are subsets of Total — Digital, Walk-in and Pop-up partition the front-of-funnel by origin, while Web Attribution is a cross-cutting credited-to-web slice.

**Backing measures / flag.** Base KPI columns (`leads`, `hot_leads`, `opportunities`, `test_drives_*`, `total_order_items`, `invoices`).

### Digital

The slice whose lead originated through a digital channel (online / web / social / digital campaign), classified from the lead source via `lead_type_mapping_new`. It is the online-acquisition funnel, as opposed to physical walk-in / pop-up traffic.

**Backing measures / flag.** Base KPI columns filtered to a digital-origin lead source.

### Walk-in

The walk-in slice: showroom visitors recorded without an originating LEAD_ID (a walk-in enquiry). It is the complement of the `*_without_walkins` measures — total `leads` = `leads_without_walkins` + walk-ins — and is flagged via `c4c_sales_offices_lkp` / the enquiry carrying no `lead_id`.

**Backing measures / flag.** Walk-in portion (`leads` − `leads_without_walkins`); walk-in flag.

### Pop-up

The pop-up slice: leads / visits captured at a temporary pop-up sales outlet rather than a permanent showroom, identified by the pop-up sales-office flag (`c4c_sales_offices_lkp`) / the `POPUP_ORG` side of the org-structure master (`eudu_mdata_dtac_orgstrc`).

**Backing measures / flag.** Base KPI columns filtered to pop-up sales offices.

### Web Attribution

The `web_attributed_*` slice: events credited to a web / social origin, including walk-ins recovered by the mobile-number back-join (`right(mobile, 9)` + division, ±120-day window) and scoped to retail / ecommerce (`sales_group IN ('001','040')`). See the "Web attribution" term for the full rule.

**Backing measures / flag.** `web_attributed_*` KPI columns.

---

See [`kpis.md`](kpis.md) for the KPI definitions.

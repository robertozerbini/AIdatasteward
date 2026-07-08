<!-- GENERATED FILE — do not edit by hand.
     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->

# Funnel 2.0 — KPI Business Glossary

_Lead-to-invoice automotive sales funnel. Report table: `prsls_ldmg_actv_dy`._

**Owner:** Sales Analytics / Data Stewardship · **Status:** approved · **Version:** 1.3.0 · **Last reviewed:** 2026-07-08

## Funnel at a glance

| # | KPI | Source | Serving stream | Measure column(s) |
|---|-----|--------|----------------|-------------------|
| 1 | **Leads** | SAP (C4C) | `CUSTOMER_LEADS` | `leads`, `leads_without_walkins` |
| 2 | **Hot Leads** | SAP (C4C) | `CUSTOMER_LEADS` | `hot_leads`, `hot_leads_without_walkins` |
| 3 | **Visits** | SAP (C4C) | `CUSTOMER_ENQUIRIES` | `opportunities`, `open_opportunities_14d` |
| 4 | **Test Drives** | SAP (C4C) | `CUSTOMER_TESTDRIVES` | `test_drives_booked`, `test_drives_completed`, `test_drives_open`, `test_drives_noshow`, `test_drives_cancelled` |
| 5 | **Total Reservations** | SAP | `CUSTOMER_ORDERS` | `total_order_items`, `orders`, `orders_with_deposite` |
| 6 | **Invoices** | SAP | `CUSTOMER_INVOICES` | `invoices` |

## Definitions

### 1. Leads

- **Source system:** SAP (C4C)  
- **KPI domain:** —  
- **Status:** approved

**Definition.** Total number of leads captured across all channels during the selected analysis period. This KPI is calculated as the count of distinct LEAD_IDs, with walk-in visits that do not have a LEAD_ID counted separately and added to the total.

**Calculation (pseudo-code).** Count distinct LEAD_IDs created within the selected analysis period, then add the count of distinct walk-in enquiries where LEAD_ID is blank or null.

**Lineage.**

- Silver source: `sap_c4c_leads`
- Gold product: `customer_leads_long`
- Serving stream: `CUSTOMER_LEADS`
- Measure column(s): `leads`, `leads_without_walkins`

> **Notes.** Org 5000 (the Automall buyer channel) is intentionally excluded in gold — a deliberate scope decision, not data loss (see the "Org 5000 (Automall buyer)" term). `leads_without_walkins` excludes pop-up / walk-in leads.

### 2. Hot Leads

- **Source system:** SAP (C4C)  
- **KPI domain:** —  
- **Status:** approved

**Definition.** Total number of qualified leads with strong purchase intent during the selected analysis period. A lead is considered qualified when its qualification is marked as Hot or when it has been passed to branch. Walk-in visits without a LEAD_ID are counted separately and added to the total.

**Calculation (pseudo-code).** Count distinct LEAD_IDs where QUALIFICATION = 'Hot' or PASS_TO_BRANCH_TIME is not blank, then add the count of distinct walk-in enquiries where LEAD_ID is blank or null.

**Lineage.**

- Silver source: `sap_c4c_leads`
- Gold product: `customer_leads_long`
- Serving stream: `CUSTOMER_LEADS`
- Measure column(s): `hot_leads`, `hot_leads_without_walkins`

> **Notes.** A subset of Leads. Qualification is `lead_qualification = 'Hot'` OR `pass_to_branch_time IS NOT NULL`.

### 3. Visits

- **Source system:** SAP (C4C)  
- **KPI domain:** —  
- **Status:** approved

**Definition.** Total number of showroom visits recorded during the selected analysis period for the chosen brand.

**Calculation (pseudo-code).** Count distinct OPPORTUNITY IDs within the selected analysis period.

**Lineage.**

- Silver source: `sap_c4c_opportunity_header`, `sap_c4c_opportunity_item`
- Gold product: `customer_enquiries_long`
- Serving stream: `CUSTOMER_ENQUIRIES`
- Measure column(s): `opportunities`, `open_opportunities_14d`

> **Notes.** A showroom visit is modelled as a C4C opportunity. `open_opportunities_14d` = opportunity still Open with a test-drive gap > 15 days. Org 5000 (Automall buyer) is intentionally excluded in gold, as for Leads.

### 4. Test Drives

- **Source system:** SAP (C4C)  
- **KPI domain:** —  
- **Status:** approved

**Definition.** Total number of test drives completed during the selected analysis period for the chosen brand.

**Calculation (pseudo-code).** Count of unique showroom visits where the related enquiry/opportunity has a test-drive activity marked as completed. Completion is identified when a C4C follow-up activity has TYPE = 'Test Drive' and STATUS = 'Completed'. The completed timestamp is derived from the latest LAST_UPDATE_DATE of the activity. The analysis period is based on this completed timestamp.

**Lineage.**

- Silver source: `sap_c4c_follow_up_activities`
- Gold product: `customer_enquiries_long`
- Serving stream: `CUSTOMER_TESTDRIVES`
- Measure column(s): `test_drives_booked`, `test_drives_completed`, `test_drives_open`, `test_drives_noshow`, `test_drives_cancelled`

> **Notes.** The headline KPI is completed test drives. Booked / Open / No-show / Cancelled are additional lifecycle measures on the same stage.

### 5. Total Reservations

- **Source system:** SAP  
- **KPI domain:** —  
- **Status:** approved

**Definition.** Total number of reservation items (sum of item quantity) created during the selected analysis period for the chosen brand.

**Calculation (pseudo-code).** Sum ITEM QUANTITY for reservation items where ORDER ITEM CREATION DATE is within the selected analysis period and ORDER TYPE IN ('Standard Order', 'Fleet Order', 'AFM Corporate Order').

**Lineage.**

- Silver source: `PAD_100_sales_document_header`, `PAD_100_sales_document_item_data`
- Gold product: `sales_ordr_vn_d`
- Serving stream: `CUSTOMER_ORDERS`
- Measure column(s): `total_order_items`, `orders`, `orders_with_deposite`

> **Notes.** Not used by BYD. Available in BYD Dashboard legacy and Funnel 2.0. Order types map to SAP codes ZOR / YOR / TA (Standard / Fleet / AFM Corporate). `item_quantity` is a line flag, so SUM counts reservation order line items. No `sales_group` filter — includes retail, fleet and corporate.

### 6. Invoices

- **Source system:** SAP  
- **KPI domain:** —  
- **Status:** approved

**Definition.** Total number of vehicle invoices generated during the selected analysis period for the selected brand. A sold vehicle invoice adds 1 to the total, while a reversed invoice subtracts 1. This gives the final number of invoices after accounting for reversals.

**Calculation (pseudo-code).** For the selected period and brand, sum the invoice transaction value: +1 for sold invoices and -1 for reversed invoices. The result is the net number of invoiced vehicles.

**Lineage.**

- Silver source: `PAD_100_billing_details_new`
- Gold product: `sales_newu_usud_sals_vn_d_view`
- Serving stream: `CUSTOMER_INVOICES`
- Measure column(s): `invoices`

> **Notes.** Net of reversals. Deduped via `flag_cancellation = 0`. New / Used split by distribution channel (10 / 20). No `sales_group` filter.

---

See [`views.md`](views.md) for how the report segments these KPIs (Total / Digital / Walk-in / Pop-up / Web Attribution), [`terms.md`](terms.md) for the supporting business vocabulary and [`../../docs/Funnel2.0.md`](../../docs/Funnel2.0.md) for full lineage.

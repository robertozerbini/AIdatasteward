<!-- GENERATED FILE — do not edit by hand.
     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->

# Funnel 2.0 — KPI Business Glossary

_Lead-to-invoice automotive sales funnel. Report table: `prsls_ldmg_actv_dy`._

**Owner:** Sales Analytics / Data Stewardship · **Status:** Under approval · **Version:** 1.1.0 · **Last reviewed:** 2026-07-07

> All definitions are **under approval** — pending steward validation, not yet signed off.

> Every KPI below can be split by **funnel group** (Digital / Walk-in / Others) — see [`funnel_groups.md`](funnel_groups.md).

## Data dictionary

| KPI | Status | Definition | Source | Pseudo code | Note |
|-----|--------|------------|--------|-------------|------|
| **Leads** | Under approval | Total number of leads captured across all channels during the selected analysis period. This KPI is calculated as the count of distinct LEAD_IDs, with walk-in visits that do not have a LEAD_ID counted separately and added to the total. | SAP (C4C) | Count distinct LEAD_IDs created within the selected analysis period, then add the count of distinct walk-in enquiries where LEAD_ID is blank or null. | Org 5000 is excluded throughout. `leads_without_walkins` excludes pop-up / walk-in leads. |
| **Hot Leads** | Under approval | Total number of qualified leads with strong purchase intent during the selected analysis period. A lead is considered qualified when its qualification is marked as Hot or when it has been passed to branch. Walk-in visits without a LEAD_ID are counted separately and added to the total. | SAP (C4C) | Count distinct LEAD_IDs where QUALIFICATION = 'Hot' or PASS_TO_BRANCH_TIME is not blank, then add the count of distinct walk-in enquiries where LEAD_ID is blank or null. | A subset of Leads. Qualification is `lead_qualification = 'Hot'` OR `pass_to_branch_time IS NOT NULL`. |
| **Visits** | Under approval | Total number of showroom visits recorded during the selected analysis period for the chosen brand. | SAP (C4C) | Count distinct OPPORTUNITY IDs within the selected analysis period. | A showroom visit is modelled as a C4C opportunity. `open_opportunities_14d` = opportunity still Open with a test-drive gap > 15 days. |
| **Test Drives** | Under approval | Total number of test drives completed during the selected analysis period for the chosen brand. | SAP (C4C) | Count of unique showroom visits where the related enquiry/opportunity has a test-drive activity marked as completed. Completion is identified when a C4C follow-up activity has TYPE = 'Test Drive' and STATUS = 'Completed'. The completed timestamp is derived from the latest LAST_UPDATE_DATE of the activity. The analysis period is based on this completed timestamp. | The headline KPI is completed test drives. Booked / Open / No-show / Cancelled are additional lifecycle measures on the same stage. |
| **Total Reservations** | Under approval | Total number of reservation items (sum of item quantity) created during the selected analysis period for the chosen brand. | SAP | Sum ITEM QUANTITY for reservation items where ORDER ITEM CREATION DATE is within the selected analysis period and ORDER TYPE IN ('Standard Order', 'Fleet Order', 'AFM Corporate Order'). | Not used by BYD. Available in BYD Dashboard legacy and Funnel 2.0. Order types map to SAP codes ZOR / YOR / TA (Standard / Fleet / AFM Corporate). `item_quantity` is a line flag, so SUM counts reservation order line items. No `sales_group` filter — includes retail, fleet and corporate. |
| **Invoices** | Under approval | Total number of vehicle invoices generated during the selected analysis period for the selected brand. A sold vehicle invoice adds 1 to the total, while a reversed invoice subtracts 1. This gives the final number of invoices after accounting for reversals. | SAP | For the selected period and brand, sum the invoice transaction value: +1 for sold invoices and -1 for reversed invoices. The result is the net number of invoiced vehicles. | Net of reversals. Deduped via `flag_cancellation = 0`. New / Used split by distribution channel (10 / 20). No `sales_group` filter. |
| **Total Open Reservations (Reservation Bank)** | Under approval · not yet implemented | Sum of reservation item quantities for open reservations as of the selected snapshot date. | SAP | Sum ITEM QUANTITY for reservation items where SALES ORDER NUMBER does not start with '0020' or '0060', REASON FOR REJECTION is blank, SECONDARY STATUS is either 'Sales Order Created' or blank. Additionally, if any duplicate VIN rows exist, they are removed. | New KPI — not yet implemented in the Funnel 2.0 pipeline; lineage and measure columns to be defined at implementation. Also known as the order bank / open orders. A stock (snapshot) measure of the open reservation bank, distinct from the Total Reservations flow KPI. |

## Lineage reference

| KPI | Silver source | Gold product | Serving stream | Measure column(s) |
|-----|---------------|--------------|----------------|-------------------|
| **Leads** | `sap_c4c_leads` | `customer_leads_long` | `CUSTOMER_LEADS` | `leads`, `leads_without_walkins` |
| **Hot Leads** | `sap_c4c_leads` | `customer_leads_long` | `CUSTOMER_LEADS` | `hot_leads`, `hot_leads_without_walkins` |
| **Visits** | `sap_c4c_opportunity_header`, `sap_c4c_opportunity_item` | `customer_enquiries_long` | `CUSTOMER_ENQUIRIES` | `opportunities`, `open_opportunities_14d` |
| **Test Drives** | `sap_c4c_follow_up_activities` | `customer_enquiries_long` | `CUSTOMER_TESTDRIVES` | `test_drives_booked`, `test_drives_completed`, `test_drives_open`, `test_drives_noshow`, `test_drives_cancelled` |
| **Total Reservations** | `PAD_100_sales_document_header`, `PAD_100_sales_document_item_data` | `sales_ordr_vn_d` | `CUSTOMER_ORDERS` | `total_order_items`, `orders`, `orders_with_deposite` |
| **Invoices** | `PAD_100_billing_details_new` | `sales_newu_usud_sals_vn_d_view` | `CUSTOMER_INVOICES` | `invoices` |
| **Total Open Reservations (Reservation Bank)** | — | — | — | — |

---

See [`funnel_groups.md`](funnel_groups.md) for the Digital / Walk-in / Others channel split, [`terms.md`](terms.md) for the supporting business vocabulary, and [`../../docs/Funnel2.0.md`](../../docs/Funnel2.0.md) for full lineage.

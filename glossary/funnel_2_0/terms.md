<!-- GENERATED FILE — do not edit by hand.
     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->

# Funnel 2.0 — Business Terms

Supporting vocabulary the KPI definitions rely on. See [`kpis.md`](kpis.md) for the KPIs themselves.

### Analysis period

The user-selected reporting date range a KPI is measured over. Each KPI declares which timestamp anchors it to the period (e.g. lead creation date, order item creation date, test-drive completion timestamp).

**Related:** _Leads_, _Test Drives_, _Total Reservations_, _Invoices_

### Chosen brand / division

The vehicle brand (SAP division) the report is filtered to. Visits, Test Drives, Total Reservations and Invoices are scoped to the selected brand.

**Related:** _Visits_, _Total Reservations_, _Invoices_

### Invoice reversal

A cancellation of a previously issued invoice. In the Invoices KPI a sold invoice contributes +1 and a reversal contributes -1, so the total is net of reversals.

**Related:** _Invoices_

### LEAD_ID

The unique identifier of a lead in SAP C4C. Distinct LEAD_IDs are the counting unit for the Leads and Hot Leads KPIs.

**Related:** _Leads_, _Hot Leads_, _Walk-in_

### OPPORTUNITY_ID

The unique identifier of a C4C opportunity. One opportunity represents one showroom visit; distinct OPPORTUNITY_IDs are the counting unit for Visits.

**Related:** _Visits_, _Test Drives_

### Order type

The SAP sales-document type classifying a reservation. Reservations count ORDER TYPE IN Standard Order (ZOR), Fleet Order (YOR) and AFM Corporate Order (TA).

**Related:** _Total Reservations_, _Reservation item_

### Org 5000 (Automall buyer)

Sales organization 5000 is the Automall buyer channel (automall / wholesale buyer traffic), not a retail showroom. The exclusion is applied only in **gold**, and only on the two front-of-funnel C4C products — `customer_leads_long` (Leads) and `customer_enquiries_long` (Visits) — via `sales_organisation_code <> '5000'`, so leads and visits drop it by design (a deliberate scope decision, not data loss). Silver retains org 5000, so its leads / visits legitimately appear as `source_only` when Silver is compared to Gold in the reconciliation drill-down; they are expected and need no fix.

**Related:** _Leads_, _Visits_

### Pass to branch

The event of handing a lead to a branch for follow-up, timestamped by PASS_TO_BRANCH_TIME. A lead with this timestamp set also qualifies as a Hot Lead, even if not explicitly marked Hot.

**Related:** _Hot Leads_

### Qualification (Hot)

The C4C lead-qualification value that marks strong purchase intent. A lead with QUALIFICATION = 'Hot' qualifies as a Hot Lead.

**Related:** _Hot Leads_

### Reservation item

A single sales-document line item of a reservation order. Total Reservations sums the item quantity (a line flag) across reservation items, so it counts line items rather than distinct orders.

**Related:** _Total Reservations_, _Order type_

### SAP C4C

SAP Cloud for Customer, the CRM system of record for the front of the funnel — leads, opportunities (visits) and follow-up activities (test drives).

**Related:** _Leads_, _Hot Leads_, _Visits_, _Test Drives_

### Test-drive activity

A C4C follow-up activity with TYPE = 'Test Drive'. Its STATUS ('Completed', open, no-show, cancelled) drives the Test Drives lifecycle measures; STATUS = 'Completed' drives the headline KPI.

**Related:** _Test Drives_

### Walk-in

A showroom visitor recorded without an originating LEAD_ID (a walk-in enquiry where LEAD_ID is blank or null). Walk-ins are counted separately and added to the Leads and Hot Leads totals so no in-person visitor is missed.

**Related:** _Leads_, _Hot Leads_, _LEAD_ID_

### Web attribution

The rule that credits a funnel event to a web / social origin, surfaced in the `web_attributed_*` counterpart of every KPI. It counts two populations: (a) events whose lead source is directly web / social, plus (b) walk-in enquiries recovered by a back-join from `customer_enquiries_long` to `customer_leads_long` on the last 9 digits of the mobile number (`right(mobile, 9)`) and division, within a ±120-day window — so a showroom walk-in that originally arrived as a web / social lead is still credited to web rather than lost. Web attribution is scoped to retail / ecommerce only via the lead back-join filter `sales_group IN ('001','040')`, so fleet / corporate and unattributed reservations are deliberately excluded by design and carry no web attribution.

**Related:** _Leads_, _Visits_, _Walk-in_

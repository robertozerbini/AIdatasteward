<!-- GENERATED FILE — do not edit by hand.
     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->

# Funnel 2.0 — Funnel Groups (Digital / Walk-in / Others)

Funnel groups classify where demand originated so every key funnel KPI (Leads → Invoices) can be reported by channel. The group is resolved from the record's normalized SOURCE, rolled up to TYPE, then to GROUP, using the lead / enquiry type mapping (`lead_type_mapping_new`).

## Groups

- **Digital** — Online / digitally-originated demand — website and app forms, ecommerce, social media, live chat / WhatsApp, CRM enquiries and the Blue app.
- **Walk-in** — In-person showroom demand with no digital origin — physical walk-ins and showroom pop-up (kiosk) leads / sales. Walk-ins typically carry no LEAD_ID and are counted separately in Leads / Hot Leads.
- **Others** — Non-digital, non-walk-in channels — B2B / fleet, events, print, SMS, telephone, lease returns (GFV / Hertz / Affinity), referrals, migrated and re-solicitation records.
- **Unclassified** — Records whose GROUP / TYPE / SOURCE do not map to any known channel (all null). Reported as Unclassified.

## How the group is identified, per KPI

| KPI | How the funnel group is identified |
|-----|------------------------------------|
| **Leads** | Native — from the lead's normalized source → type → GROUP. Walk-ins are leads originating at a pop-up / walk-in sales office (typically no LEAD_ID); Digital / Others come from `lead_type_mapping_new`. |
| **Hot Leads** | Same as Leads (Hot Leads is a qualified subset of Leads and inherits its group). |
| **Visits** | Native — from the opportunity / enquiry source → type → GROUP. |
| **Test Drives** | Inherited from the parent enquiry's group (a test drive is a follow-up activity on the enquiry). |
| **Total Reservations** | Inherited from the linked enquiry via `enquiry_id`; Digital is captured as the `web_attributed_*` measures through the lead back-join (`sales_group IN ('001','040')`). Orders with no enquiry link are Unclassified for group. |
| **Invoices** | Inherited from the linked order → enquiry (`sales_order_number → enquiry_id`); Digital via the `web_attributed_*` back-join, same as Total Reservations. |
| **Total Open Reservations (Reservation Bank)** | Not yet implemented — will follow the Total Reservations rule (inherited from the linked enquiry) once the metric is built. |

## Classification mapping (SOURCE + TYPE → GROUP)

The authoritative lookup, applied via `lead_type_mapping_new`. Rows marked ⚠ are parsing assumptions pending confirmation.

| GROUP | TYPE | SOURCE | |
|-------|------|--------|--|
| — | — | — |  |
| Digital | Blue | Book A Service | ⚠ |
| Digital | Blue | General Enquiry |  |
| Digital | Blue | Loan Eligibility Form |  |
| Digital | Blue | Mobile Service |  |
| Digital | Blue | Sell Your Car Form |  |
| Digital | Blue | Test Drive Form |  |
| Digital | Crm | General Enquiry |  |
| Digital | Live Chat | Cec |  |
| Digital | Live Chat | Live Chat |  |
| Digital | Live Chat | V24 |  |
| Digital | Live Chat | Whatsapp |  |
| Digital | Live Chat | Whatsapp Chatbot |  |
| Digital | Social | Bulk Lead |  |
| Digital | Social | Facebook |  |
| Digital | Social | Instagram |  |
| Digital | Social | Linkedin |  |
| Digital | Social | Snapchat |  |
| Digital | Social | Tiktok |  |
| Digital | Social | Youtube |  |
| Digital | Web | Ai Sales Agent |  |
| Digital | Web | Carswitch |  |
| Digital | Web | Dubizzle |  |
| Digital | Web | Ecomm |  |
| Digital | Web | Email |  |
| Digital | Web | Enquiry Form |  |
| Digital | Web | Finance Form |  |
| Digital | Web | Google Analytics |  |
| Digital | Web | Inbound Call |  |
| Digital | Web | Insider |  |
| Digital | Web | Internal |  |
| Digital | Web | Loan Eligibility Form |  |
| Digital | Web | Offer Form |  |
| Digital | Web | Outbound Call |  |
| Digital | Web | Principle Website |  |
| Digital | Web | Sell Your Car Form |  |
| Digital | Web | Test Drive Form |  |
| Digital | Web | Trade-in Form |  |
| Digital | Web | Web Chatbot |  |
| Digital | Web | Web Form |  |
| Others | — | — |  |
| Others | Aff Lease | — | ⚠ |
| Others | B2b | Campaign |  |
| Others | B2b | Field Visit |  |
| Others | B2b | General Enquiry |  |
| Others | B2b | Referral |  |
| Others | B2b | Repeat Purchase |  |
| Others | B2b | Walk-in |  |
| Others | Events | Events |  |
| Others | Events | Gov Program |  |
| Others | Events | Trade Fair |  |
| Others | Gfv Return | — |  |
| Others | Hertz Lease Return | — |  |
| Others | Others | Migrated |  |
| Others | Others | Others |  |
| Others | Others | Reference |  |
| Others | Print | Newspaper |  |
| Others | Showroom | Promotions |  |
| Others | Showroom | Resolicitation |  |
| Others | Sms | Sms |  |
| Others | Telephone | — |  |
| Others | Telephone | Telephone |  |
| Others | Web | — |  |
| Others | Web | Re-solicitation | ⚠ |
| Walk-in | Pop-up Lead | Pop-up | ⚠ |
| Walk-in | Pop-up Sales | Pop-up | ⚠ |
| Walk-in | Walk-in | Ghq Id |  |
| Walk-in | Walk-in | Walk-in |  |
| Walk-in | Walk-in | Warrah |  |

---

See [`kpis.md`](kpis.md) for the KPI definitions this dimension splits.

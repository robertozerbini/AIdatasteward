<!-- GENERATED FILE — do not edit by hand.
     Edit glossary.yaml and run: python glossary/funnel_2_0/render_glossary.py -->

# Funnel 2.0 — Funnel Groups (Digital / Walk-in / Others)

Funnel groups classify where demand originated so every key funnel KPI (Leads → Invoices) can be reported by channel. The group is resolved from the record's normalized SOURCE, rolled up to TYPE, then to GROUP, using the lead / enquiry type mapping (`lead_type_mapping_new`).

## Groups

- **Digital** — Online / digitally-originated demand — website and app forms, ecommerce, social media, live chat / WhatsApp, CRM enquiries and the Blue app.
- **Walk-in** — In-person showroom demand with no digital origin — physical walk-ins and showroom pop-up (kiosk) leads / sales. Walk-ins typically carry no LEAD_ID and are counted separately in Leads / Hot Leads.
- **Others** — Non-digital, non-walk-in channels — B2B / fleet, events, print, SMS, telephone, showroom promotions / re-solicitation, generic product / offer / appointment / prospect enquiries, referrals and migrated records.
- **Unclassified** — Records whose GROUP / TYPE / SOURCE do not map to any known channel (all null). Reported as Unclassified.

## How the group is identified, per KPI

| KPI | How the funnel group is identified |
|-----|------------------------------------|
| **Leads** | Native — from the lead's normalized source → type → GROUP. Walk-ins are leads originating at a pop-up / walk-in sales office (typically no LEAD_ID); Digital / Others come from `lead_type_mapping_new`. |
| **Hot Leads** | Same as Leads (Hot Leads is a qualified subset of Leads and inherits its group). |
| **Visits** | Native — from the opportunity / enquiry source → type → GROUP. |
| **Test Drives** | Inherited from the parent enquiry's group (a test drive is a follow-up activity on the enquiry). |
| **Total Reservations** | Inherited from the linked enquiry via `enquiry_id`; Digital is captured as the `web_attributed_*` measures through the lead back-join (`sales_group IN ('001','040')`). Orders with no enquiry link are Unclassified for group. |
| **Total Reservation (Proposed — active orders)** | Proposed — same enquiry-inherited grouping as Total Reservations, just restricted to active reservations (not rejected; latest secondary status 'Sales Order Created' or blank). |
| **Invoices** | Inherited from the linked order → enquiry (`sales_order_number → enquiry_id`); Digital via the `web_attributed_*` back-join, same as Total Reservations. |
| **Total Open Reservations (Reservation Bank)** | Not yet implemented — will follow the Total Reservations rule (inherited from the linked enquiry) once the metric is built. |

## Classification mapping (lead_source + lead_type → lead_group)

The authoritative lookup (66 rows), applied via `lead_type_mapping_new`. `null` = no source value.

| lead_group | lead_type | lead_source |
|------------|-----------|-------------|
| Digital | Live Chat | Whatsapp |
| Digital | Social | Instagram |
| Digital | Web | Sell Your Car Form |
| Digital | Live Chat | V24 |
| Digital | Web | Outbound Call |
| Digital | Live Chat | Whatsapp Chatbot |
| Digital | Blue | Loan Eligibility Form |
| Digital | Web | Offer Form |
| Digital | Social | Bulk Lead |
| Digital | Social | Linkedin |
| Digital | Web | Dubizzle |
| Digital | Web | Web Chatbot |
| Digital | Blue | General Enquiry |
| Digital | Social | Tiktok |
| Digital | Web | Trade-in Form |
| Digital | Web | Enquiry Form |
| Digital | Web | Ai Sales Agent |
| Digital | Blue | Test Drive Form |
| Digital | Web | Inbound Call |
| Digital | Social | Facebook |
| Digital | Web | Loan Eligibility Form |
| Digital | Web | Test Drive Form |
| Digital | Social | Youtube |
| Digital | CRM | General Enquiry |
| Digital | Web | Carswitch |
| Digital | Web | Insider |
| Digital | Web | Web Form |
| Digital | Social | Snapchat |
| Digital | Web | Finance Form |
| Digital | Web | Google Analytics |
| Digital | Live Chat | Cec |
| Digital | Web | Principle Website |
| Digital | Web | Email |
| Digital | Web | Internal |
| Digital | Live Chat | Live Chat |
| Digital | Blue | Book A Service |
| Digital | Blue | Sell Your Car Form |
| Others | SMS | Sms |
| Others | TELEPHONE | `null` |
| Others | B2B | General Enquiry |
| Others | Showroom | Resolicitation |
| Others | Others | Others |
| Others | Others | Reference |
| Others | Telephone | Telephone |
| Others | B2B | Campaign |
| Others | WEB | `null` |
| Others | Showroom | Promotions |
| Others | Others | Migrated |
| Others | ENQUIRY ABOUT PRODUCTS | `null` |
| Others | B2B | Bulk Lead |
| Others | B2B | Repeat Purchase |
| Others | B2B | Field Visit |
| Others | B2B | Walk-in |
| Others | B2B | Referral |
| Others | Events | Trade Fair |
| Others | APPOINTMENT REQUEST | `null` |
| Others | Events | Events |
| Others | PROSPECT | `null` |
| Others | Print | Newspaper |
| Others | ENQUIRY ABOUT OFFER | `null` |
| Others | Events | Gov Program |
| Walk-in | Walk-In | Walk-in |
| Walk-in | Walk-In | Warrah |
| Walk-in | Pop-up | Sales Pop-up |
| Walk-in | Pop-up | Lead Pop-up |
| Walk-in | Walk-In | Ghq Id |

---

See [`kpis.md`](kpis.md) for the KPI definitions this dimension splits.

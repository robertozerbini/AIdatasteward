-- =============================================================================
-- Funnel 2.0 — Customer Journey / Drop-off Analysis
-- =============================================================================
-- Answers four stewardship questions against the Funnel 2.0 report table:
--   Q1. At which stages do customers most frequently exit the journey?
--   Q2. Lead -> Hot Lead conversion.
--   Q3. What are the key reasons for customer drop-off at each stage?
--   Q4. Which journey steps have the lowest conversion / highest abandonment?
--
-- Dialect: Databricks / Spark SQL.
--
-- SOURCE TABLE (pick the env you run against):
--   dev  : discovery_auto.auto_dev.prsls_ldmg_actv_dy
--   uat  : discovery_auto.auto_analytics.prsls_ldmg_actv_dy   <- current notebook target
--   prod : prod_auto.gold_serve.prsls_ldmg_actv_dy
-- Queries below use the PROD name; swap it for your environment.
--
-- READ THIS FIRST — what the data can and cannot tell you
-- -----------------------------------------------------------------------------
-- * prsls_ldmg_actv_dy is a DAILY AGGREGATE (one row per reporting_date x org /
--   division / group / office x channel x sales exec x make/model x funnel group
--   x type/source). It is NOT a per-customer event log — there is no per-lead
--   stage-transition table here. So "exit / drop-off" is measured as the DROP IN
--   VOLUME between one stage's measure and the next, not by tracking individual
--   customers from stage to stage.
-- * Cross-stage drop-off is an expected TREND, not a hard invariant: a lead
--   created in one period can convert (visit / test-drive / reserve / invoice) in
--   a LATER period ("stage lag"). Over a long, stable window the ratios are a fair
--   proxy for conversion; over a short window the later stages look artificially
--   low. Keep the window wide (a full quarter+) for headline conversion figures.
-- * Headline stage measures (journey order):
--     1 Leads        -> leads
--     2 Hot Leads    -> hot_leads
--     3 Visits       -> opportunities
--     4 Test Drives  -> test_drives_completed   (entered = test_drives_booked)
--     5 Reservations -> total_order_items        (distinct orders = orders)
--     6 Invoices     -> invoices
--   All of these are authoritative column names from the business glossary
--   (glossary/funnel_2_0/glossary.yaml).
-- * REASON columns (Q3) are only captured at the C4C stages. Column names marked
--   "-- VERIFY" below are inferred from the lineage notes (lost_oppo_*,
--   enquiry_status_reason, lead lost reasons) — confirm them against the physical
--   schema of prsls_ldmg_actv_dy before productionising Q3.
-- * `group` is the funnel-group dimension (Digital / Walk-in / Others) and is a
--   reserved word, so it is back-ticked as `group` throughout.
--
-- Set the analysis window once here (used by every query):
--   :start_date / :end_date are Databricks SQL parameter markers; if your runner
--   doesn't bind them, replace with literals e.g. DATE'2026-01-01'.
-- =============================================================================


-- =============================================================================
-- Q1 + Q4.  Full funnel: stage volumes, stage-to-stage conversion, drop-off,
--           and abandonment — ranked so the biggest exits surface at the top.
-- -----------------------------------------------------------------------------
-- One pass builds the period totals, unpivots them into ordered stages, then
-- LAG() compares each stage to the one before it.
--   conversion_rate   = this_stage / previous_stage      (higher = better)
--   dropoff_count     = previous_stage - this_stage       (who left before here)
--   dropoff_rate      = 1 - conversion_rate               (= abandonment rate)
-- The stage with the largest dropoff_rate is where customers most frequently
-- exit (Q1); ordering by dropoff_rate DESC also answers Q4.
-- =============================================================================
WITH totals AS (
  SELECT
    SUM(leads)                 AS s1_leads,
    SUM(hot_leads)             AS s2_hot_leads,
    SUM(opportunities)         AS s3_visits,
    SUM(test_drives_completed) AS s4_test_drives,
    SUM(total_order_items)     AS s5_reservations,
    SUM(invoices)              AS s6_invoices
  FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
  WHERE reporting_date BETWEEN :start_date AND :end_date
),
stages AS (
  SELECT 1 AS stage_no, 'Leads'        AS stage, s1_leads       AS stage_count FROM totals
  UNION ALL SELECT 2, 'Hot Leads',        s2_hot_leads   FROM totals
  UNION ALL SELECT 3, 'Visits',           s3_visits      FROM totals
  UNION ALL SELECT 4, 'Test Drives',      s4_test_drives FROM totals
  UNION ALL SELECT 5, 'Reservations',     s5_reservations FROM totals
  UNION ALL SELECT 6, 'Invoices',         s6_invoices    FROM totals
),
ranked AS (
  SELECT
    stage_no,
    stage,
    stage_count,
    LAG(stage_count) OVER (ORDER BY stage_no) AS prev_count,
    LAG(stage)       OVER (ORDER BY stage_no) AS prev_stage,
    FIRST_VALUE(stage_count) OVER (ORDER BY stage_no) AS top_of_funnel
  FROM stages
)
SELECT
  stage_no,
  prev_stage || ' -> ' || stage                              AS step,
  stage_count,
  prev_count,
  -- who dropped between the previous stage and this one
  (prev_count - stage_count)                                 AS dropoff_count,
  ROUND(stage_count / NULLIF(prev_count, 0), 4)              AS conversion_rate,      -- higher = better
  ROUND(1 - stage_count / NULLIF(prev_count, 0), 4)          AS dropoff_rate,         -- = abandonment at this step (Q4)
  -- cumulative view: share of the original leads still alive at this stage
  ROUND(stage_count / NULLIF(top_of_funnel, 0), 4)           AS pct_of_leads
FROM ranked
WHERE prev_count IS NOT NULL          -- drop the Leads row (no prior stage to exit from)
ORDER BY dropoff_rate DESC;           -- <- biggest exit / highest abandonment first  (Q1 & Q4)


-- =============================================================================
-- Q2.  Lead -> Hot Lead conversion.
-- -----------------------------------------------------------------------------
-- (a) Overall for the window.
-- =============================================================================
SELECT
  SUM(leads)                                          AS leads,
  SUM(hot_leads)                                      AS hot_leads,
  ROUND(SUM(hot_leads) / NULLIF(SUM(leads), 0), 4)    AS lead_to_hot_conversion,
  ROUND(1 - SUM(hot_leads) / NULLIF(SUM(leads), 0),4) AS lead_dropoff_rate
FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
WHERE reporting_date BETWEEN :start_date AND :end_date;

-- (b) By funnel group (Digital / Walk-in / Others) — shows which channels
--     actually qualify. NB: per the glossary every walk-in enquiry is counted as
--     a Hot Lead, so Walk-in will read ~100% by design (a known simplification).
SELECT
  `group`                                             AS funnel_group,
  SUM(leads)                                          AS leads,
  SUM(hot_leads)                                      AS hot_leads,
  ROUND(SUM(hot_leads) / NULLIF(SUM(leads), 0), 4)    AS lead_to_hot_conversion
FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
WHERE reporting_date BETWEEN :start_date AND :end_date
GROUP BY `group`
ORDER BY leads DESC;

-- (c) Monthly trend of the Lead -> Hot Lead conversion (excluding walk-ins, so
--     the trend reflects genuine qualification rather than the walk-in default).
SELECT
  DATE_TRUNC('MONTH', reporting_date)                                             AS month,
  SUM(leads_without_walkins)                                                      AS leads_ex_walkins,
  SUM(hot_leads_without_walkins)                                                  AS hot_leads_ex_walkins,
  ROUND(SUM(hot_leads_without_walkins) / NULLIF(SUM(leads_without_walkins),0), 4) AS lead_to_hot_conversion
FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
WHERE reporting_date BETWEEN :start_date AND :end_date
GROUP BY DATE_TRUNC('MONTH', reporting_date)
ORDER BY month;


-- =============================================================================
-- Q3.  Key reasons for drop-off at each stage.
-- -----------------------------------------------------------------------------
-- Reasons only exist where SAP C4C records them. There is no single "reason"
-- column that spans the whole funnel, so this is one query per stage that has a
-- reason signal, unioned into a single ranked list.
--
-- Column names marked "-- VERIFY" are inferred from the lineage docs
-- (CUSTOMER_LEADS "lost reasons", CUSTOMER_ENQUIRIES enquiry_status_reason,
-- lost_oppo_* breakdowns). Confirm against the physical schema before relying
-- on them. The test-drive block uses fully-authoritative lifecycle columns.
-- =============================================================================

-- (3a) Visit / enquiry stage — the richest reason signal (why opportunities die).
--      enquiry_status_reason is joined in from ENQUIRY_STATUS_REASON_MAP.
SELECT
  'Visits (enquiry lost)'                 AS stage,
  COALESCE(enquiry_status_reason, 'Unknown / not captured') AS reason,   -- VERIFY column name
  SUM(opportunities)                      AS opportunities,
  ROUND(100 * SUM(opportunities)
        / NULLIF(SUM(SUM(opportunities)) OVER (), 0), 2) AS pct_of_stage
FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
WHERE reporting_date BETWEEN :start_date AND :end_date
  AND enquiry_status_reason IS NOT NULL           -- keep only lost/closed enquiries   -- VERIFY
GROUP BY enquiry_status_reason
ORDER BY opportunities DESC;

-- (3b) Test-drive stage — abandonment reasons are the lifecycle states themselves.
--      These columns ARE authoritative (note the schema typo test_drives_oepn = open).
SELECT
  'Test Drives'          AS stage,
  reason,
  cnt,
  ROUND(cnt / NULLIF(booked, 0), 4) AS share_of_booked
FROM (
  SELECT
    SUM(test_drives_booked)    AS booked,
    SUM(test_drives_noshow)    AS noshow,
    SUM(test_drives_cancelled) AS cancelled,
    SUM(test_drives_oepn)      AS still_open,
    SUM(test_drives_completed) AS completed
  FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
  WHERE reporting_date BETWEEN :start_date AND :end_date
) t
LATERAL VIEW STACK(
  4,
  'No-show',            t.noshow,
  'Cancelled',          t.cancelled,
  'Still open (stalled)', t.still_open,
  'Completed (converted)', t.completed
) s AS reason, cnt
ORDER BY cnt DESC;

-- (3c) Reservation stage — reservations that never picked up a deposit are the
--      soft drop-off signal (orders_with_deposite is the committed subset), and
--      orders with no enquiry link are the attribution gap called out in the docs.
SELECT
  'Reservations'                                                       AS stage,
  SUM(orders)                                                          AS orders,
  SUM(orders_with_deposite)                                            AS orders_with_deposit,
  (SUM(orders) - SUM(orders_with_deposite))                            AS orders_without_deposit,
  ROUND(1 - SUM(orders_with_deposite) / NULLIF(SUM(orders), 0), 4)     AS no_deposit_rate
FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
WHERE reporting_date BETWEEN :start_date AND :end_date;

-- (3d) Lead stage — lost-lead reasons (CUSTOMER_LEADS stream carries lost reasons).
--      lost_oppo_* / lead-lost-reason columns are NOT confirmed in this repo —
--      template only; replace the column name once the physical schema is known.
-- SELECT
--   'Leads (lost)'                          AS stage,
--   lead_lost_reason                        AS reason,          -- VERIFY column name
--   SUM(leads)                              AS leads
-- FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
-- WHERE reporting_date BETWEEN :start_date AND :end_date
--   AND lead_lost_reason IS NOT NULL                            -- VERIFY
-- GROUP BY lead_lost_reason
-- ORDER BY leads DESC;


-- =============================================================================
-- Q4.  Lowest conversion / highest abandonment — ranked league table.
-- -----------------------------------------------------------------------------
-- Same stage spine as Q1 but presented purely as a ranking of the worst steps,
-- and sliced by funnel group so you can see WHERE a step is worst (e.g. Digital
-- vs Walk-in). Aggregate (all-group) rows carry funnel_group = 'ALL'.
-- =============================================================================
WITH g AS (
  SELECT
    COALESCE(`group`, 'Unclassified') AS funnel_group,
    SUM(leads)                 AS s1,
    SUM(hot_leads)             AS s2,
    SUM(opportunities)         AS s3,
    SUM(test_drives_completed) AS s4,
    SUM(total_order_items)     AS s5,
    SUM(invoices)              AS s6
  FROM prod_auto.gold_serve.prsls_ldmg_actv_dy
  WHERE reporting_date BETWEEN :start_date AND :end_date
  GROUP BY ROLLUP(`group`)                       -- gives per-group rows + a grand total
),
gg AS (
  SELECT
    CASE WHEN funnel_group IS NULL THEN 'ALL' ELSE funnel_group END AS funnel_group,
    s1, s2, s3, s4, s5, s6
  FROM g
),
steps AS (
  SELECT funnel_group, 1 AS step_no, 'Leads -> Hot Leads'         AS step, s2 AS num, s1 AS den FROM gg
  UNION ALL SELECT funnel_group, 2, 'Hot Leads -> Visits',        s3, s2 FROM gg
  UNION ALL SELECT funnel_group, 3, 'Visits -> Test Drives',      s4, s3 FROM gg
  UNION ALL SELECT funnel_group, 4, 'Test Drives -> Reservations', s5, s4 FROM gg
  UNION ALL SELECT funnel_group, 5, 'Reservations -> Invoices',   s6, s5 FROM gg
)
SELECT
  funnel_group,
  step,
  den                                             AS entered_step,
  num                                             AS reached_next,
  ROUND(num / NULLIF(den, 0), 4)                  AS conversion_rate,   -- lowest = worst
  ROUND(1 - num / NULLIF(den, 0), 4)              AS abandonment_rate   -- highest = worst
FROM steps
WHERE den IS NOT NULL AND den > 0
ORDER BY abandonment_rate DESC, funnel_group;

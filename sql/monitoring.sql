-- Monitoring & reporting views/queries over prod_auto.gold_virtual.dq_results.
-- Run this once to create the views; the queries below back dashboards + alerts.

-- =====================================================================
-- Views
-- =====================================================================

-- Latest result per (target, check) — "current health".
CREATE OR REPLACE VIEW prod_auto.gold_virtual.v_dq_latest AS
SELECT * EXCEPT (rn) FROM (
  SELECT *,
         row_number() OVER (
           PARTITION BY target, check_type, check_name
           ORDER BY run_ts DESC
         ) AS rn
  FROM prod_auto.gold_virtual.dq_results
)
WHERE rn = 1;

-- One row per run (a run_id) with pass/fail rollup and whether it gated.
CREATE OR REPLACE VIEW prod_auto.gold_virtual.v_dq_runs AS
SELECT
  run_id,
  min(run_ts)                                   AS run_ts,
  max(trigger)                                  AS trigger,
  max(target)                                   AS target,
  max(check_type)                               AS check_type,
  count(*)                                       AS checks,
  sum(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS failed,
  max(CASE WHEN gated THEN 1 ELSE 0 END) = 1     AS gated
FROM prod_auto.gold_virtual.dq_results
GROUP BY run_id;

-- =====================================================================
-- Reporting queries (dashboard tiles)
-- =====================================================================

-- 1) Current health per target: how many checks are failing right now.
-- SELECT target, check_type,
--        count(*) AS checks,
--        sum(CASE WHEN status='fail' THEN 1 ELSE 0 END) AS failing
-- FROM prod_auto.gold_virtual.v_dq_latest
-- GROUP BY target, check_type
-- ORDER BY failing DESC;

-- 2) Failures in the last 24h (feeds the alert below).
-- SELECT run_ts, target, check_type, check_name, severity, expected, actual, details
-- FROM prod_auto.gold_virtual.dq_results
-- WHERE status = 'fail' AND run_ts >= current_timestamp() - INTERVAL 24 HOURS
-- ORDER BY run_ts DESC;

-- 3) Gated runs (blocked a pipeline) in the last 7 days.
-- SELECT run_ts, target, check_type, failed
-- FROM prod_auto.gold_virtual.v_dq_runs
-- WHERE gated AND run_ts >= current_timestamp() - INTERVAL 7 DAYS
-- ORDER BY run_ts DESC;

-- 4) Per-check failure trend (daily) — for a time-series chart.
-- SELECT date_trunc('DAY', run_ts) AS day, target, check_name,
--        sum(CASE WHEN status='fail' THEN 1 ELSE 0 END) AS failures
-- FROM prod_auto.gold_virtual.dq_results
-- GROUP BY 1, 2, 3
-- ORDER BY day;

-- 5) KPI drift: actual vs expected over time for KPI checks.
-- SELECT run_ts, check_name, expected, actual, (actual - expected) AS diff
-- FROM prod_auto.gold_virtual.dq_results
-- WHERE check_type = 'kpi'
-- ORDER BY run_ts DESC;

-- =====================================================================
-- Alert query — return >0 rows only when there is a NEW failure to notify on.
-- Point a Databricks SQL Alert at this and it fires on non-empty result.
-- =====================================================================
-- SELECT target, check_type, check_name, severity, run_ts, actual, expected
-- FROM prod_auto.gold_virtual.dq_results
-- WHERE status = 'fail'
--   AND run_ts >= current_timestamp() - INTERVAL 1 HOURS
-- ORDER BY severity, run_ts DESC;

-- Unified results store: every check kind (rowlevel / endpoint / kpi) appends here.
CREATE TABLE IF NOT EXISTS prod_auto.gold_virtual.dq_results (
  run_id      STRING,
  run_ts      TIMESTAMP,
  trigger     STRING,      -- pipeline | schedule | ondemand
  target      STRING,
  check_type  STRING,      -- rowlevel | endpoint | kpi
  check_name  STRING,
  severity    STRING,      -- error | warn
  status      STRING,      -- pass | fail
  expected    DOUBLE,
  actual      DOUBLE,
  details     STRING,      -- JSON
  gated       BOOLEAN      -- true = error-severity failure that blocks downstream
) USING DELTA;

-- KPI ground truth: editable by data stewards, versioned by effective dates.
CREATE TABLE IF NOT EXISTS prod_auto.gold_virtual.dq_kpi_ground_truth (
  kpi_name       STRING,
  target         STRING,
  expected_value DOUBLE,
  tolerance_pct  DOUBLE,   -- nullable
  tolerance_abs  DOUBLE,   -- nullable
  effective_from TIMESTAMP,
  effective_to   TIMESTAMP, -- nullable = open-ended
  active         BOOLEAN
) USING DELTA;

-- Example seed row:
-- INSERT INTO prod_auto.gold_virtual.dq_kpi_ground_truth VALUES
-- ('total_revenue_2026q2','revenue_kpis', 1250000.0, 1.0, NULL,
--  timestamp('2026-04-01'), NULL, true);

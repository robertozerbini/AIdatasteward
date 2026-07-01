# dq_framework — Notifications (email · Teams · Jira)

Failures can be routed to multiple channels — **email**, **Microsoft Teams**, and
**Jira** (creates an issue) — with a single config that decides *who* is notified
for *which* failures. Everything is driven by
[`configs/notifications.yaml`](../configs/notifications.yaml).

## How it fits together

```
results (from any check kind)
        │
        ▼
core.routing.build_notifications(results, routes)   ← WHO + WHICH channel  (unit-tested)
        │
        ▼
core.messages.render(results)  → subject, body      ← message content       (unit-tested)
        │
        ▼
notify.dispatch → channel adapters (email / teams / jira)   ← delivery       (runtime)
```

Routing and message rendering are pure and unit-tested; only the delivery
adapters touch the network.

## Config: channels + routes

`configs/notifications.yaml` has two sections:

**`channels`** — the connections. Secrets are references, resolved at runtime via
Databricks secrets (never stored in plaintext):
```yaml
channels:
  email:
    type: email
    from_addr: dq-bot@yourco.com
    smtp_host: smtp.yourco.com
    smtp_port: 587
    user:     {secret: {scope: dq, key: smtp_user}}
    password: {secret: {scope: dq, key: smtp_password}}
  teams_dq:
    type: teams
    webhook: {secret: {scope: dq, key: teams_webhook}}
  jira_dq:
    type: jira
    base_url: https://yourco.atlassian.net
    project_key: DQ
    issue_type: Bug
    user:  {secret: {scope: dq, key: jira_user}}
    token: {secret: {scope: dq, key: jira_token}}
```

**`routes`** — WHO gets WHICH failures. A route matches a failed result when
every key in `match` equals the result's field (empty `match` = catch-all). One
failure can match several routes.
```yaml
routes:
  - match: {severity: error}                 # gating failures
    channels: [teams_dq, jira_dq, email]     # Teams + Jira ticket + email
    email_to: [dq-oncall@yourco.com]

  - match: {severity: warn}                  # warnings
    channels: [teams_dq, email]
    email_to: [dq-digest@yourco.com]

  - match: {target: sp_customer_360}         # per-target override
    channels: [email]
    email_to: [customer360-team@yourco.com]
```
Match keys are any result field: `severity`, `target`, `check_type`, `check_name`.

## Where to configure the people to notify

`email_to` on each route is the recipient list; `channels` picks the delivery
mechanisms. To change who's paged, edit the routes — no code change. Team-level
distribution lists are recommended over individuals.

## Wiring it to runs

Three ways, in order of precedence:

1. **Per call** — `run_row_checks(df, config=..., notify="configs/notifications.yaml")`
2. **CLI / job task** — `dq-run --config ... --notify .../configs/notifications.yaml`
3. **Embedded in the check config** — add a `notifications:` key pointing at the
   file (or an inline mapping):
   ```yaml
   kind: rowlevel
   target: ...
   notifications: /Workspace/.../configs/notifications.yaml
   ```
Notifications are sent only when there is at least one failed check.

## Secrets setup (one-time)

```bash
databricks secrets create-scope dq
databricks secrets put-secret dq teams_webhook   # paste the Teams incoming-webhook URL
databricks secrets put-secret dq jira_user       # Jira account email
databricks secrets put-secret dq jira_token       # Jira API token
databricks secrets put-secret dq smtp_user
databricks secrets put-secret dq smtp_password
```
- **Teams:** channel → Connectors → *Incoming Webhook* → copy the URL.
- **Jira:** Atlassian account → Security → *API tokens* → create; user is the
  account email, `project_key` is the target project.

## Relationship to native Databricks notifications

For plain email/Teams-on-job-failure you can also use **Databricks job
`email_notifications` / webhook destinations** (see
[MONITORING.md](MONITORING.md)). Use this framework notifier when you need
**Jira issue creation** or **per-target / per-severity routing** that native
job notifications don't express.

## Testing without sending

`dispatch(results, config, secret_resolver=...)` accepts an injected secret
resolver, and the routing/rendering are covered by `tests/test_routing.py` and
`tests/test_messages.py`. To dry-run delivery on a cluster, point channels at a
test webhook / a personal Jira sandbox project before going live.

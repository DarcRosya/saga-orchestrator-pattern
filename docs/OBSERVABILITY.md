# Observability Runbook

This runbook covers only the parts that are easy to misread in this project: saga business metrics and quick diagnostics.

## What Is Measured

### Event metrics (counters)
- `saga_execution_total{status="success|compensated|stuck|compensation_attempted"}`
- `saga_step_execution_total{step,status}`
- `saga_step_duration_seconds{step}`

Use these for rates, trends, and incident timelines.

### State metric (gauge)
- `saga_manual_intervention_required_current`

Use this for the current amount of unresolved manual cases.

## Gauge Source of Truth

`saga_manual_intervention_required_current` is not incremented/decremented manually.
It is synchronized from the database by scheduler worker logic:

- `sync_manual_intervention_gauge` in `src/workers/scheduler.py`
- SQL source: `COUNT(*) FROM orders WHERE global_status='MANUAL_INTERVENTION_REQUIRED'`
- Update call: `SAGA_MANUAL_STUCK_CURRENT.set(count)`

When synchronization runs:

- Every scheduler poll cycle (`poll_and_dispatch_orders`, each 30s)
- After dead-order check (`check_and_alert_dead_orders`, each 10m)
- Immediately after admin force cancel via queued task `sync_manual_intervention_gauge`

This model avoids drift if status is changed by admin actions or direct DB maintenance.

## Why Counter and Gauge Both Exist

- Counter answers: "How many new incidents happened in a time window?"
- Gauge answers: "How many incidents exist right now?"

For operations, the stuck panel should use gauge. For postmortem and trend analysis, use counters.

## Dashboard Interpretation

### Compensation Health (Attempted vs Success)
- `Attempted`: `sum(increase(saga_execution_total{status="compensation_attempted"}[1m]))`
- `Successful`: `sum(increase(saga_execution_total{status="compensated"}[1m]))`

`Attempted - Successful` approximates compensations that did not complete in the same window.

### Why values can be fractional (e.g. 2.67)

`increase()` may return non-integer values on short windows due to scrape-time interpolation. This is normal in Prometheus.

If you need integer-looking bars, use:

```promql
sum(round(increase(saga_execution_total{status="compensation_attempted"}[1m])))
sum(round(increase(saga_execution_total{status="compensated"}[1m])))
```

### p99 latency panel and "1 second limit"

The dashboard p99 query uses `http_request_duration_seconds_bucket`.
If this histogram has only low buckets (for example `0.1, 0.5, 1.0, +Inf`), tail visibility above 1 second is coarse and may look visually capped.

In this project, lower buckets were expanded in API instrumentation to:
`0.1, 0.5, 1, 2.5, 5, 10, 30, 60`.

After deploy/restart, wait for new samples before evaluating p99 trend changes.

## Fast Diagnostics Checklist

1. Scheduler gauge target is up:

```promql
up{job="saga_scheduler_worker"}
```

2. Current stuck count from metrics:

```promql
saga_manual_intervention_required_current
```

3. Current stuck count from DB (must match eventually):

```sql
select count(*)
from orders
where global_status = 'MANUAL_INTERVENTION_REQUIRED';
```

4. Worker event counters available:

```promql
saga_execution_total
```

5. Expected propagation delay:
- scheduler sync cycle: up to 30s
- Prometheus scrape interval: typically 15s

Total visible delay up to around 45s is expected.

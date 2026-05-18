# Scheduler Module

## Scope

The scheduler module runs periodic collection and testing jobs in-process.

## Key Files

- `proxypool/scheduler/jobs.py` defines `SchedulerService`.

## Implementation Notes

`SchedulerService.start()` imports APScheduler lazily, creates a UTC `BackgroundScheduler`, and registers two interval jobs:

- `collector-job` calls `CollectorService.collect_from_sources(sources)`.
- `tester-job` runs `TesterService.run_batch()` via `asyncio.run()`.

Intervals and tester limits/concurrency are supplied by API route parameters. `stop()` shuts the background scheduler down without waiting for jobs to finish.

The newer auto-task loop in `proxypool/api/app.py` handles configurable subscription refresh, tester, and speed-test tasks through `TaskManager`; this scheduler module remains the simpler explicit `/api/scheduler/start` and `/api/scheduler/stop` implementation.

## Tests

Scheduler behavior is mostly exercised indirectly through API route tests and service-level tests for collector/tester behavior.

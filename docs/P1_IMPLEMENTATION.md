# P1 correctness and workflow completion

P0 is committed as `2af6fea`. This document describes the subsequent P1 changes. Use [the deployment guide](P0_IMPLEMENTATION.md) for installation and [the operations runbook](OPERATIONS.md) for recovery and monitoring.

## Migration

Run `alembic upgrade head` from `backend/` with the intended application configuration. Compose's bootstrap does this before API startup. Revision `0006_p1_integrity_monitoring` adds:

- Unique `(model_id, version)` identities, permitted stage checks, and one Production version per model.
- Unique feature-group identities per environment and feature names per group.
- Durable scheduled-minute identities for jobs.
- Training baseline histograms, version-specific inference observations, and recorded drift runs.

The migration stops if existing data has duplicate identities, multiple Production versions for a model, or unsupported stage names. Its error identifies the diagnostic query. Resolve those records deliberately before retrying; the migration never deletes, renames, or silently archives existing data. Do not apply the fresh-install SQL script over an existing deployment as an upgrade mechanism.

## Recorded drift monitoring

Model artifact upload registers its feature IDs in version lineage. The Link Features control can also attach training features and a dataset URI; features required by a supported artifact cannot be removed from lineage. No unrelated feature fallback or guessed source tables are used.

1. Submit numeric samples from the version's actual training frame to `POST /models/{model_id}/versions/{version_id}/drift-baseline`. Include `window_start`, `window_end`, and `samples: {feature_id: [numbers...]}`. Each supplied feature needs at least two finite samples and must be linked to this version. At most 100 features / 100000 total samples are accepted.
2. Baselines store fixed bin boundaries, counts, sample counts and training-window timestamps. A new capture creates an immutable snapshot; it does not overwrite historical evidence.
3. Successful `POST /models/{id}/predict` calls persist the numeric feature values actually used, exact version, entity key and observation timestamp. Runtime-only inputs without registered feature IDs are outside this feature-drift report.
4. Submit `POST /models/{id}/drift/runs` with the version string, observation `window_start`/`window_end`, and optional `min_samples` (default 20, minimum 2). Windows are UTC, start inclusive / end exclusive, at most 31 days and 100000 inference observations.
5. Runs compare recorded inference values with the latest version baseline's fixed bins. Empty bins use normalized pseudocount smoothing. PSI can be exactly zero. Insufficient samples produce a null score and null drift decision, never a fabricated healthy value. The numeric PSI thresholds are indicators for review, not automatic model-promotion decisions.
6. `GET /models/{id}/drift?version=...` reads stored evidence without running a measurement. History contains actual recorded runs only, scoped to the current baseline. Capturing a new baseline starts a new comparison history while retaining previous database records.

The console exposes baseline capture, version/window selection, sample counts, explicit missing-data states and measurement history. Measurements are requested explicitly; use an authenticated external schedule to submit windows if continuous evaluation is needed. Categorical distributions and drift over unregistered runtime-only fields are outside the current numeric PSI interface.

## Feature identity and event semantics

Online serving, historical joins and ingestion share one resolver. Supported references are UUID, bare name, `group:name`, and `environment/group:name`; batch, join and ingestion requests can specify an `environment` filter. Unknown or ambiguous references fail with HTTP 422. Group names cannot contain `/` or `:`, and new feature names use identifier characters.

For backward compatibility, single unambiguous bare/UUID requests return bare feature names. Explicitly qualified requests retain their reference keys. If multiple UUIDs identify features with the same name, response keys become `environment/group:name` so values cannot overwrite each other. The `features` response list identifies the returned keys. Requesting the same physical feature twice through aliases is rejected.

- Timestamps without an offset are interpreted as UTC; responses and stored times use UTC.
- The newest event timestamp wins online. A late event may be added to offline history while leaving a newer online value unchanged.
- Replaying the same entity/feature/event timestamp with the exact same stored value is a no-op. A different value at that timestamp returns HTTP 409 and rolls back the whole batch. Historical values are not silently amended.
- `ingested_count` is the number of validated records processed. `online_updated_count` is the number of accepted online changes; replayed and late records can contribute zero.
- Point-in-time joins include the value at the exact observation timestamp and exclude all later events.
- Requests are bounded: 100 features, 1000 entities/observations, 10000 feature-observation join pairs, and 10000 streaming records.

## Scheduler coordination

Cron expressions are five-field UTC schedules. Create and update validate the expression, supported job type, payload shape, UUID and feature existence before persistence. `PUT /jobs/{id}` updates the complete definition; the console provides edit, pause, resume and manual trigger controls. A paused schedule can still be triggered manually.

Every worker refreshes definitions from PostgreSQL every five seconds. Scheduled callbacks recheck the current cron and active flag before execution. A session advisory lock prevents overlapping workers from running the same job, including manual/scheduled overlap. A unique `(job_definition_id, scheduled_for)` minute prevents a second execution of the same scheduled occurrence after the first finishes.

Materialization failures propagate to failed job runs and readable logs. If a worker disconnects, PostgreSQL releases its execution lock; the next acquired execution marks abandoned running records failed. Scheduled slots provide at-most-once dispatch; they are not automatically retried after a crash. An operator can review the feature/materialization record and trigger a manual retry. Exactly-once behavior for arbitrary external side effects is not claimed; the implemented job type only materializes features.

## Registry and administration transactions

Version creation and promotion lock the parent model row. Promotion archives the previous Production version, then updates stage/history/audit in the same transaction. Unique and partial unique constraints preserve the rules across concurrent requests. Re-promoting the current stage is idempotent. Only Staging, Production and Archived are accepted.

User creation validates all roles before inserting a user, then commits user, role links and audit together. API key creation/revocation is also audited in its mutation transaction. API keys retain the owner's current roles and active-user checks; keys are visible in plaintext once, are hashed in storage, and become unusable after revocation. Non-admin users can manage only their own keys through the API; the Administration console remains admin-only.

## Console and operations

The console supports artifact upload/download, version-specific input selection, runtime input JSON, feature linking, accurate source/consumer edges and unknown-source states. Native modal dialogs provide labelled dialog semantics, explicit Tab/Shift+Tab focus wrapping, Escape dismissal and focus restoration. Form controls have associated labels. Pages expose load/submit errors with retry paths, and route/navigation permissions match the jobs/admin API policy.

The service badge polls actual readiness. Redis fallback is shown explicitly. Dashboard freshness compares each active feature's latest event time with its declared cadence: streaming 5 minutes, hourly 1 hour, daily 1 day, weekly 7 days. Missing data is stale; unsupported cadence is reported as unknown. With no eligible active features, the percentage is N/A, not 100%. This is a feature-level latest-event policy, not an assertion that every entity has fresh data.

## Validation

The backend regression suite covers concurrent version creation/promotions, scheduled-slot/lock deduplication, rollback on audit failure, role/API-key permissions, exact online/historical values, scoped identity collisions, event replays, actual drift observations and honest readiness/freshness states. Browser checks exercise creation/materialization, promotion/history, artifact round trips, linking, drift capture/measurement, schedule editing, permission-aware navigation and service failures.

`examples/01_churn_prediction_e2e.py` creates its own definitions and model, reconstructs 40 historical observations, trains with a held-out split, uploads learned JSON coefficients, freezes the training baseline, verifies 40 served probabilities, and stores PSI from actual inference observations. The second registered-model example remains available. Run both with:

```powershell
python scripts/run-ml-examples.py --env-file .env.docker --url http://localhost:5173/api
```

Both require scikit-learn and httpx and real configured administrator credentials; neither substitutes simulated weights or silently skips missing setup. CI runs the examples after the fresh-stack/browser checks. Remote CI results still require a push/run; local verification does not imply a completed GitHub Actions run.

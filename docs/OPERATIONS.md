# Operations, backup and recovery

## Monitoring

- Check `/api/health` for process liveness and `/api/ready` for migrated database access, the restricted source reader and writable artifact storage. Alert on sustained non-2xx readiness responses.
- Redis failure keeps readiness available through PostgreSQL and reports `cache: postgres_fallback`. Alert separately if that state persists, since performance differs from cache-backed serving.
- Poll authenticated `/api/jobs/overview` for failed runs, timestamps and logs. Alert on new failed run IDs and on an expected scheduled occurrence missing beyond its cadence plus operational grace period.
- Review `/api/features/{id}/materializations` for rejected source data or SQL errors. Review recorded drift runs for sufficient sample counts and actual observation windows; null scores are not healthy measurements.
- Collect container stdout/stderr and retain job/materialization records. Source SQL errors, cache publication failures and scheduler exceptions are logged. Configure the external monitoring system's destination and recipients in the deployment; the application does not send unsolicited messages.

The UI reports readiness and feature-level event freshness. It does not replace an external availability check. The built-in cron timezone is UTC.

## Consistent backups

Back up PostgreSQL, artifact files, the private deployment configuration and the application revision together. Quiesce incoming writes and scheduler execution while taking a backup, or use a coordinated database snapshot plus artifact snapshot with the same consistency point. The PostgreSQL database contains artifact keys and all lineage, role, baseline, inference-observation and drift-run records; copying only model files is insufficient.

For the bundled stack, use a maintenance window. These example commands assume the repository root and an existing `.env.docker`:

```powershell
New-Item -ItemType Directory -Force backups
docker compose --env-file .env.docker stop frontend backend
docker compose --env-file .env.docker exec -T db pg_dump -U postgres -d feature_store -Fc -f /tmp/feature_store.dump
docker compose --env-file .env.docker cp db:/tmp/feature_store.dump backups/feature_store.dump
docker compose --env-file .env.docker run --name featureops-artifact-backup --no-deps backend python -c "import shutil; shutil.make_archive('/tmp/artifacts','gztar','/app/storage','artifacts')"
docker cp featureops-artifact-backup:/tmp/artifacts.tar.gz backups/artifacts.tar.gz
docker rm featureops-artifact-backup
docker compose --env-file .env.docker start backend frontend
```

The named maintenance container mounts the artifact volume and remains available until the archive is copied; the final command removes only that finished helper. Use a distinct helper name if another backup container with that name exists. Store the private configuration separately from source control. Archive backups in access-controlled storage and retain successful restore-test evidence.

## Restore procedure

Restore into a separate project/database first. Keep application writers stopped. Load the PostgreSQL dump with `pg_restore` into the empty target database, restore the `artifacts/` directory to the configured artifact volume, and configure the matching deployment secrets. Provision the restricted source reader and grants for that database. Check the restored `alembic_version` before running newer migrations.

Do not run a destructive `pg_restore --clean` against a populated deployment without an explicit replacement decision and a recoverable backup. Prefer a new target and switch routing after validation. Do not extract an untrusted archive into application storage; use the archive produced by your controlled backup process.

After restore, verify readiness, administrator login, role enforcement, a feature lookup, historical data, an artifact download/hash, registered inference and stored drift history. Validate before resuming scheduled work. The verification scripts in `scripts/` can validate artifact bytes and predictions against a saved state for disposable local stacks.

## Failure recovery

- For a failed materialization, inspect its error. The data transaction rolls back while the failure record is retained. Fix the source SQL, restricted-reader grants or invalid source values before retrying.
- For a worker disconnect, inspect the job and feature materialization records. A later lock owner marks abandoned runs failed. Automatic scheduled slots are not replayed; use a reviewed manual trigger if another attempt is needed.
- For cache loss, PostgreSQL remains authoritative. Missing or expired Redis keys read the database; new successful writes republish the current generation. Old cache generations cannot override committed values.
- For a missing artifact, restore the matching volume or upload an appropriate artifact through the managed endpoint. Arbitrary `file://` paths are not a recovery mechanism.
- If a P1 migration stops on duplicate identities or multiple Production versions, run the reported diagnostic query, choose the intended identities/stages, preserve the affected records/history, and retry the migration.

Define backup frequency, retention, alert grace periods and recovery objectives for the deployment's workload. P2 load/latency testing is still required before making capacity promises.

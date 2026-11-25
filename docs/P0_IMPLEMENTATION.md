# P0 implementation and operation

## Fresh local installation

Use Docker Compose with Python 3.10+ available for the configuration helper:

```powershell
python scripts/configure-docker.py
docker compose --env-file .env.docker up --build -d --wait
```

Open http://localhost:5173. Sign in with `ADMIN_EMAIL` and the generated `ADMIN_PASSWORD` from `.env.docker`. The helper refuses to overwrite an existing configuration. Keep that file private. Database and API ports are internal; the public API is at `/api` on the frontend origin.

Startup waits for PostgreSQL, runs Alembic migrations, creates roles and the initial administrator, provisions a separate source SQL reader, then starts the API and frontend. An empty sample source table exists by default. Set `SEED_DEMO_DATA=true` before startup for optional sample data, a demonstration linear model artifact, and a materialization schedule. The seeded model is illustrative; the trained example below verifies real learned coefficients.

The artifact volume and database volume survive container replacement. To stop the stack while retaining data, use `docker compose --env-file .env.docker down`. Do not use `down -v` unless deleting the data is intended. Environment credential changes do not rotate existing administrator or PostgreSQL accounts; perform account/password rotation explicitly.

## Source SQL configuration

`DATABASE_URL` is the application writer. `SOURCE_DATABASE_URL` must use a separate login with no elevated attributes or role memberships. SQL previews and materializations execute through the source connection in PostgreSQL read-only transactions with statement/lock timeouts and bounded results. Materialization rejects oversized results rather than publishing a truncated refresh.

The bundled bootstrap provisions a reader on the same PostgreSQL database using an administrative writer connection. Only `feature_store.sample_events` is granted by default. For additional sources, an operator creates tables in the `sources` schema, sets `SOURCE_ALLOWED_TABLES=sources.table_one,sources.table_two`, and reruns bootstrap. Table names are validated identifiers. Grant only the source objects intended for this application; do not grant application schemas or privileged/security-definer functions to the reader. If removing an allowed table from configuration, revoke its previous reader grant explicitly.

For an external managed PostgreSQL service, have its administrator provision the restricted reader and grants, then set both URLs. Automatic provisioning requires the same database and sufficient role-management privileges. On a host installation, run migrations and initial setup with `python -m app.db.bootstrap` from `backend/`; for an externally provisioned source, run Alembic and the seed script separately. Configure the reader before starting query workflows.

Reader checks fail closed on elevated roles, memberships, or access to sensitive application tables. SQL runs on a connection separate from the transaction publishing feature values. A source query error cannot leave the feature write session in an aborted state.

## Validation and atomic refreshes

`validation_rules_json` accepts only `allow_null`, `required_type`, `min_value`, and `max_value`. Rules must be a JSON object; bounds must be finite and ordered. Supported types are float/number/double, int/integer, string/str, and bool/boolean. The declared feature type is enforced when `required_type` is absent. Non-finite numbers and failed numeric conversions are rejected.

The policy is **reject the entire batch**. Streaming ingestion validates every row before writing. Materialization validates the bounded source result, then updates offline and online values in one transaction. Any failure rolls back the values; the failed materialization record is then committed separately. Scheduled jobs propagate that failure. Offline writes are idempotent for an identical entity/feature/event timestamp. Newer online event timestamps take precedence over late arrivals.

## Redis consistency

PostgreSQL stores `FeatureDefinition.online_revision`. Every online write/refresh advances this revision in the transaction updating values. Cache keys use `fs:v2:{feature_id}:{revision}:{entity_key}` and JSON-encoded values, preserving null, empty string, and zero.

Redis publication runs only after successful PostgreSQL commit. Rollbacks discard queued publications. Cache misses, expiry, and outages read PostgreSQL. If a publication fails, reads cannot reach the previous revision's stale cached value. Replacing a feature's entire materialization also advances the revision, invalidating removed entities. Connections are reused, and a temporary Redis outage does not permanently disable later cache attempts. Expired generations are removed by the configured cache TTL.

## Registered model runtime

The supported executable serving format is `featureops.linear.v1` JSON for binary logistic classification or linear regression. It stores a real trained model's coefficients/intercept and ordered typed inputs. Arbitrary binaries can be stored/downloaded, but pickle/ONNX files are not executed by this runtime; prediction returns a validation error for unsupported formats.

Example artifact, replacing the UUID with an actual feature ID:

```json
{
  "format": "featureops.linear.v1",
  "task": "binary_classification",
  "inputs": [
    {"name": "spend", "feature_id": "11111111-1111-1111-1111-111111111111", "dtype": "float"},
    {"name": "cart_size", "dtype": "int"}
  ],
  "coefficients": [0.25, -0.1],
  "intercept": -1.5,
  "classes": [0, 1]
}
```

Inputs with a `feature_id` are hydrated from the feature store; inputs without one must be supplied in `runtime_features`. Unknown runtime fields and attempts to override stored-feature inputs are rejected. Missing or invalid inputs return HTTP 422. The artifact signature determines feature order/types; hydration never falls back to arbitrary features. Feature references must exist. For regression, the response prediction contains `value`; classification returns `probability`, `prediction_class`, and `label`.

Upload through `POST /models/{model_id}/versions/{version_id}/artifact`. A version can be scored explicitly through its version string, or implicitly after promotion to Production. No automatic fallback to a Staging version occurs. The console promotion flow displays persisted stage history, available again after reload through each row's History action.

To export a scikit-learn binary logistic model, use `coef_[0].tolist()`, `float(intercept_[0])`, and `classes_.tolist()` in the artifact above. Inputs must match the order and preprocessing used during fitting. Pipelines requiring additional transformations need to export compatible transformed features or another runtime implementation.

Run the self-contained trained example with `scikit-learn` and `httpx` installed:

```powershell
$env:FEATURE_STORE_URL = 'http://localhost:5173/api'
$env:ADMIN_EMAIL = 'admin@featureops.local'
# Set ADMIN_PASSWORD from your private configuration.
python examples/02_registered_logistic_model.py
```

It creates its own feature/model/version, trains a classifier, uploads learned coefficients, promotes it, and checks the served probability against scikit-learn. The older churn tutorial awaits the separate P1 repair.

## Artifact storage boundary

The service generates opaque `artifact://{model_uuid}/{version_uuid}/{storage_uuid}` keys. Supplied filenames cannot select directories. Reads validate the key's ownership and resolved storage-root containment. Version creation rejects caller-supplied artifact URIs; legacy `file://`/external URIs require re-upload before download/serving. Files are streamed into temporary files, bounded by `ARTIFACT_MAX_BYTES` (50 MiB default), then atomically renamed. Failed metadata commits remove the new file. Previous uploads are retained; automatic storage garbage collection is outside P0.

## Production routing and configuration

The default frontend uses relative `/api` URLs. Vite proxies them in development and Nginx proxies them in Docker, so a remote browser talks to the server it opened. `VITE_API_URL` is an optional **build-time** override; changing it requires rebuilding the frontend image.

For production, terminate HTTPS at your ingress/reverse proxy and forward the site to the frontend service. Keep `VITE_API_URL=/api`, set `APP_ENV=production`, and list the exact public HTTPS origin in `CORS_ORIGINS`. Production rejects missing reader configuration, predictable JWT secrets, placeholder administrator credentials, and wildcard/non-HTTPS CORS settings. Generate JWT secrets with at least 32 random characters and administrator passwords with at least 12 characters. TLS certificates and public DNS are deployment-specific and are not automatically provisioned by this local Compose stack.

`/health` is liveness; `/ready` checks migrated application tables and restricted source-query execution. Redis outages remain serviceable through PostgreSQL fallback. The default deployment runs one scheduler-owning API process; distributed scheduler coordination remains P1 work.

## Verification

```powershell
docker compose -p featureops-p0-test -f docker-compose.test.yml up -d --wait
python -m pip install -r backend/requirements-test.txt
python -m pytest backend/tests -q
```

Use the backend virtual environment if dependencies are installed there. Tests explicitly ignore the configured application database. `TEST_DATABASE_URL` can override the disposable test database but must end in `_test`; test fixtures truncate application data in that database. `TEST_REDIS_URL` overrides the disposable Redis connection. CI provisions both services and runs migrations/fixtures automatically.

Browser tests target a disposable local Compose stack. Set `P0_ENV_FILE` to the private Docker env file (resolved from `frontend/`) and `P0_BASE_URL` to the site's local URL; the default verification stack uses `.cache/p0-stack.env` and port 5188. Then run `npm ci`, `npx playwright install chromium`, and `npm run test:e2e` in `frontend/`. They create fixtures, sign in, promote a model, reload its history, exercise registered inference, and verify same-origin ingestion/SQL-denial behavior.

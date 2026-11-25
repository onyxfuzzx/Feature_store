# Feature Store & Model Registry

FeatureOps defines SQL features, stores online and historical values, and serves registered linear/logistic models through FastAPI, a React console, and a Python SDK. P0, P1, and P2 repository work is implemented and locally verified. Production capacity, public deployment, and package publication require deployment-specific validation.

## Start locally

Install Docker with Compose and Python 3.11 or newer for the configuration helper. From the repository root:

```powershell
python scripts/configure-docker.py
docker compose --env-file .env.docker up --build -d --wait
```

Open http://localhost:5173. Use `ADMIN_EMAIL` and the generated `ADMIN_PASSWORD` in `.env.docker`. Keep that file private; the helper refuses to overwrite it. Startup migrates PostgreSQL, initializes the administrator/roles and a restricted source reader, then starts the API. Source data is empty unless `SEED_DEMO_DATA=true` is configured. The frontend proxies `/api` to the backend; PostgreSQL, Redis, and the API use internal container ports.

Stop with `docker compose --env-file .env.docker down` to retain data. `down -v` deletes the database and artifact volumes. Changing environment credentials does not rotate existing accounts.

## Implemented behavior

- SQL feature groups, typed validation, read-only SQL previews and atomic materialization in bounded source chunks.
- PostgreSQL online values with an optional Redis cache using transactional revision invalidation, miss filling, expiry and database fallback.
- Indexed point-in-time historical joins. Exact event replays are idempotent; conflicting same-timestamp events fail atomically and late events cannot replace newer online values.
- Registered model versions, managed artifact upload/download, feature linkage, transactional stage history and one Production version per model.
- Executable `featureops.linear.v1` JSON artifacts for binary logistic classification and linear regression, with ordered typed inputs. Stored pickle/ONNX binaries are downloadable but are not executed.
- Version-specific immutable training histograms, recorded inference observations and explicit numeric PSI measurements over UTC windows. Missing/insufficient observations remain unknown.
- Validated UTC cron jobs, pause/edit/resume, cross-worker advisory locks and durable scheduled-slot deduplication. Crash-interrupted slots require an explicit retry decision.
- Four roles (`admin`, `ml_engineer`, `data_scientist`, `analyst`), hashed user-owned API keys, JWT sessions, audit history, readiness, lineage and accessible console dialogs.
- SDK context management, structured API/transport errors, paginated iterators, and CLI token authentication.

The offline table is indexed and **not partitioned**. Streaming is HTTP push. Native Kafka/Kinesis consumers, warehouse connectors, SSO, tenant isolation, additional model runtimes and automatic SDK publication are extensions.

## Architecture and runtime scope

React 18 / Vite 8 / React Router 7 is served by Nginx. FastAPI / SQLAlchemy / Alembic use PostgreSQL 16; Redis 7 is optional for online reads. Artifacts persist on a separate volume. The source SQL reader has a separate restricted database login.

Backend and SDK validation targets Python **3.11, 3.12 and 3.13** on Linux; frontend development targets Node **24 and 26**. Docker uses Python 3.11 and Node 24. Windows contributors can run the same Linux containers through Docker Desktop. Native Windows dependency installation uses the input requirements and is not the reproducible release environment.

Runtime/test Python dependencies are pinned with hashes; frontend dependencies use exact versions and `npm ci`. See [contributing](CONTRIBUTING.md) for clean environment checks and dependency updates.

## Guides and evidence

- [P0 installation, configuration and artifact format](docs/P0_IMPLEMENTATION.md)
- [P1 identity, drift, scheduler and browser behavior](docs/P1_IMPLEMENTATION.md)
- [P2 performance and release changes](docs/P2_IMPLEMENTATION.md)
- [Measured performance and request limits](docs/PERFORMANCE.md)
- [Backup, recovery and operations](docs/OPERATIONS.md)
- [System behavior and training-to-serving flow](docs/END_TO_END_BLUEPRINT.md)
- [Milestones and remaining extensions](milestone.md)
- [SDK lifecycle, errors and CLI](sdk/README.md)
- [Contributing](CONTRIBUTING.md), [conduct](CODE_OF_CONDUCT.md), [security reporting](SECURITY.md)

The OpenAPI schema is available at http://localhost:5173/api/openapi.json while the stack is running. Runnable learned-model workflows are in `examples/`; `scripts/run-ml-examples.py` checks both against a running stack. Local test results are recorded in the P2 guide. Remote GitHub Actions execution and public release publication have not been observed in this session.

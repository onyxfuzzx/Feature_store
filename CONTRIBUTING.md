# Contributing

Use Python 3.11-3.13, Node 24 or 26, and Docker Compose. Follow the [community conduct](CODE_OF_CONDUCT.md) and report vulnerabilities through [SECURITY.md](SECURITY.md).

## Reproducible backend checks

From the repository root:

```powershell
docker compose -p featureops-test -f docker-compose.test.yml up -d --wait
docker build -f backend/Dockerfile.test --build-arg PYTHON_VERSION=3.11 -t featureops-test .
docker run --rm --network featureops-test_default featureops-test
```

Repeat the build with `PYTHON_VERSION=3.12` or `3.13` to check those runtimes. Tests explicitly require a disposable database ending in `_test`, migrate/seed it and isolate artifact storage. They never use `backend/.env`. Do not point test configuration at an application database.

For Linux host development, create a virtual environment and install `backend/requirements-test.txt` with `pip install --require-hashes -r backend/requirements-test.txt`, then `pip install --no-deps --no-build-isolation -e sdk`. Start the disposable services above; tests default to their loopback ports 55432/56379. Run `pytest backend/tests`.

On native Windows, install `backend/requirements-test.in` instead because the lock is resolved for Linux and includes platform-specific dependencies. Use containers for release-equivalent validation.

```sh
ruff check backend sdk examples scripts
ruff format --check backend sdk examples scripts
sh scripts/verify-sdk.sh
pip-audit -r backend/requirements.txt --no-deps --disable-pip
```

The package script builds a wheel from the source distribution, checks metadata, installs the wheel, exercises imports/CLI outside the checkout, and installs the source distribution. It does not publish packages.

## Frontend checks

From `frontend/`:

```sh
npm ci
npm run lint
npm run format:check
npm run build
npm audit
```

Use `npm run format` or `ruff format ...` to apply formatting. Hook dependencies and unused imports are enforced. To run the console in development, start the API and use `npm run dev`; default `/api` is proxied to localhost:8000. For browser tests, start a fresh app stack with the README commands, install Chromium with `npx playwright install chromium`, set `P0_BASE_URL=http://localhost:5173` and `P0_ENV_FILE=../.env.docker`, then run `npm run test:e2e`. Never use production credentials for these mutating workflows.

## Dependency updates and review

Edit `backend/requirements.in` or `backend/requirements-test.in`, then resolve the hash locks in Linux Python 3.11:

```powershell
docker run --rm --mount "type=bind,source=${PWD},target=/work" -w /work python:3.11-slim sh scripts/compile-requirements.sh
```

Commit inputs and both generated locks together. Upgrade frontend packages explicitly and commit `package.json` with `package-lock.json`. Run audits and the supported runtime checks after dependency changes. Docker base tags receive upstream fixes and are not byte-for-byte pinned images.

Keep changes focused, explain behavior and validation in the PR, and include migrations for database changes. Alembic is the startup migration authority; keep `database/schema.sql` aligned as a reference snapshot. CI runs the checks above plus fresh-stack browser, learned-model and artifact-persistence workflows. Benchmarks are opt-in using a separate `_bench` database; see [performance](docs/PERFORMANCE.md).

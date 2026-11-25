# P2 implementation and release validation

P2 items 18 and 19 are implemented. This guide records repository behavior and
local verification; remote GitHub Actions status, public deployment and package
publication are outside the evidence collected here.

## Performance

- Historical observations use one indexed lateral-lookup statement instead of
  one ORM query per observation/feature. Duplicate observation order, absent
  values and exact timestamp boundaries are preserved.
- Feature-reference batches resolve in one query; streaming resolves and parses
  each distinct reference/rule once per request. User roles are batched.
- Job overview pages use one definitions query and one indexed latest-five-runs
  query, independent of the number of jobs on the page.
- Source SQL uses a server-side cursor. Materialization validates and writes
  chunks atomically, including exact/conflicting replay handling across chunk
  boundaries. Refresh cache invalidation occurs once and warms on read; the
  complete source result is not retained for Redis publication.
- Offline/online writes use bulk upserts with explicit timestamp/conflict
  handling. New covering indexes are installed by migration
  `0007_p2_lookup_indexes`. Existing writes/read consistency tests remain green.
- List endpoints and console/SDK consumers implement bounded pagination with
  continuation headers. See [performance](PERFORMANCE.md) for exact limits,
  measured results, repetition commands and retention/partition decisions.

Apply migrations through the normal bootstrap path before running the new
code. Index creation is transactional and can block writers while building;
measure index-build time and schedule a maintenance window for large existing
tables. `database/schema.sql` is a reference; Alembic controls upgrades.

## Dependencies and contributor checks

Python inputs and generated hash locks cover runtime and development packages.
Docker and CI install with `--require-hashes`. The release environment is Linux;
native Windows development uses the input files. Frontend dependencies are
exact and `npm ci` consumes its lock. Vite/React Router were updated after audit
findings; PyJWT replaces python-jose and its advisory-affected dependency chain.
Existing HS256 tokens using the same signing key and claims remain compatible.
Regression checks reject expired tokens, wrong signatures and wrong algorithms.

Ruff enforces Python lint/imports and formatting; ESLint checks JavaScript,
React keys and hooks, and Prettier enforces frontend formatting. Adding these
checks also normalized existing source formatting and removed unused code.
CI targets Python 3.11/3.12/3.13 and Node 24/26 and runs runtime/frontend dependency
audits. Container base tags remain updateable and should be reviewed separately
from Python/npm package locks. Audits are point-in-time checks.

## SDK and release scope

The SDK closes owned clients and preserves caller-owned sessions. API errors
carry status/detail; transport exceptions are wrapped with their cause and
finite timeouts. There are no automatic write retries. Catalog iterators follow
pagination without collecting all records. List methods preserve their list
return type by collecting those iterators.

CLI login prompts for passwords when absent from options/environment, emits a
token only with explicit `--show-token`, accepts JWT/API-key environment values
and always closes its client. Credentials are not automatically saved.

`scripts/verify-sdk.sh` builds wheel/sdist artifacts, validates metadata, installs
the wheel, checks imports/CLI outside the checkout and installs the sdist. CI
repeats this without publishing. The README, architecture, milestones,
contributing, security and Code of Conduct describe the actual supported scope.

## Local verification

Verified locally on 2026-11-25:

| Check | Result |
| --- | --- |
| PostgreSQL/Redis backend tests, clean Linux Python 3.11 | **94 passed** |
| Same suite, clean Linux Python 3.12 | **94 passed** |
| Same suite, clean Linux Python 3.13 | **94 passed** |
| Browser workflows against rebuilt Compose app | **9 passed** |
| Node 24 container and Node 26 host lint/format/build | Passed |
| Python Ruff lint and formatting | Passed; 81 files checked |
| SDK wheel/sdist metadata, installation, outside-checkout imports and CLI | Passed on Python 3.11 and 3.12 |
| Runtime pip-audit and frontend npm audit | No known vulnerabilities reported |
| Benchmark | 100,000 historical rows; one historical statement, two job-overview statements; zero concurrent workload errors |
| Trained churn example | 40 reconstructed rows, held-out accuracy 0.875, 40 matching served probabilities, persisted PSI |
| Registered logistic example | Served probability matched learned coefficients |
| Fresh startup and final Compose readiness | Passed with generated private credentials and demo seeding disabled |
| Artifact persistence after API container replacement | SHA-256 and registered prediction matched saved state |

The two long browser workflows initially exceeded the old 30-second total test
budget during host/build contention. Their total workflow budget is now 120
seconds, preserving the value, accessibility and authorization assertions; the
final complete run passed. Tests use dedicated disposable databases and isolated
artifacts, separate from the application database.

Compose exposes source grants/timeouts/row limits, chunk size, Redis TTL and
artifact size through matching environment variables, with the defaults in the
performance guide. Changes to these limits require recreating the application
services and workload-specific validation.

Known scope limits: benchmark HTTP is in-process and local, offline storage is
unpartitioned, retention requires an operator decision, inference supports only
the JSON linear/logistic runtime, and package publication/public deployment
have not been performed. Upstream Starlette currently warns that its httpx
TestClient adapter is deprecated; tests still pass, and this does not affect
the deployed Uvicorn API or httpx SDK transport.

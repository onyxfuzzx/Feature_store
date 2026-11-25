# Performance measurements and operating limits

Measured 2026-11-25. The [raw result](benchmarks/p2-local.json) records versions,
sample counts and percentiles. These are local development measurements, not a
production SLO or a universal sub-10ms latency guarantee.

## Workload and results

Linux containers on Docker Desktop/WSL2, x86-64, 12 visible logical CPUs,
Python 3.11.18, PostgreSQL 16, Redis 7, FastAPI 0.165.0 and SQLAlchemy 2.1.9.
Other local development tasks shared the host. The harness uses in-process
FastAPI TestClient HTTP with real PostgreSQL and Redis over the Docker network.
External HTTP server, proxy, TLS and wide-area network time are excluded. CPU,
driver memory and database buffers are not isolated or controlled.

The initial dataset has 100,000 offline rows: 1,000 entities × 5 features × 20
hourly events, with 5,000 online rows. There are 100 jobs and 1,000 runs. The
historical workload reconstructs 100 observations × 5 features between events.
The concurrent workload uses 8 workers, 160 reads and 40 single-record writes;
writes to the same feature invalidate its generation. It asserts known values
and fails on any request error. Materialization reads 10,000 rows in chunks of
1,000, including repeated idempotent refreshes.

| Operation | Samples | p50 ms | p95 ms | p99 ms |
| --- | ---: | ---: | ---: | ---: |
| Historical join service, 100 × 5 | 100 | 3.944 | 6.962 | 8.401 |
| Previous per-pair lookup reference, same dataset/index | 20 | 411.160 | 1060.665 | 1060.665 |
| Warm online HTTP, 20 entities × 5 | 100 | 13.561 | 17.558 | 18.041 |
| Historical HTTP, 100 × 5 | 100 | 17.958 | 27.842 | 34.027 |
| Concurrent reads, 8 shared workers | 160 | 156.819 | 237.874 | 252.809 |
| Concurrent writes, 8 shared workers | 40 | 184.340 | 243.740 | 243.817 |
| Materialize 10,000 rows | 5 | 9629.298 | 10427.591 | 10427.591 |

The historical value operation uses **one SQL statement instead of 500**. The
100-job overview uses **two SQL statements** excluding authentication/role checks.
HTTP timings include validation, authorization and serialization; service SQL
timings do not. The reference comparison retains the same P2 index and is not
an end-to-end benchmark of a previous checkout.

Concurrent requests completed with **zero errors**, approximately 37.72 reads/s
and 9.43 writes/s over their shared elapsed interval. A separate traced
materialization peaked at **5,065,327 bytes** of Python allocations and retained
zero post-commit cache publication entries. This is not whole-process RSS or
PostgreSQL/Redis memory. Source/result construction, writes, validation and
transaction commit are included in materialization time; its traced memory run
is separate from timing samples.

Percentiles use the sorted sample at `floor((n-1)*p)`. With only five refreshes
and twenty reference samples the tail estimates are coarse; repeated runs and
larger samples are required for capacity decisions. Redis misses/outages are
covered by integration tests but are not a separate latency series here.

## Repeat the benchmark

From the repository root in PowerShell:

```powershell
docker compose -p featureops-bench -f docker-compose.bench.yml up -d --wait
docker build -f backend/Dockerfile.test -t featureops-benchmark .
docker run --rm --network featureops-bench_default --mount "type=bind,source=${PWD},target=/work" -w /work featureops-benchmark python scripts/benchmark.py --database-url postgresql+psycopg2://postgres:disposable-benchmark-password@db:5432/featureops_bench --redis-url redis://redis:6379/0 --output .cache/benchmark.json
```

The script clears feature/model/job data only in the selected dedicated
`*_bench` database. Never reuse an application database or shared cache for it.
The Compose benchmark credentials are disposable fixtures bound to loopback on
the host. `--samples` defaults to 100 and must be at least 20. Keep the raw report,
host configuration and workload together when comparing runs. Stop the
benchmark services with the same Compose project and file when finished.

## Bounds and pagination

| Interface | Bound |
| --- | --- |
| Online batch | 1-1,000 entities, 1-100 features, at most 10,000 pairs |
| Historical join | 1-1,000 observations, 1-100 features, at most 10,000 pairs |
| Streaming ingestion | 1-10,000 records per atomic request |
| SQL preview | 1-50 rows |
| Materialization | `SOURCE_MAX_ROWS=100000` default; exceeding it fails the entire refresh |
| Source chunk | `MATERIALIZATION_BATCH_SIZE=1000` default, configurable 1-5,000 |
| Source statement/lock timeout | `SOURCE_QUERY_TIMEOUT_MS=5000` default, configurable 1-60,000 |
| Managed artifact | `ARTIFACT_MAX_BYTES=52428800` default |
| Paginated collection | `limit=100` default, 1-500; `offset=0` default, 0-1,000,000 |

Feature/group catalogs, models/versions, materialization histories, jobs/overviews/
runs, users/audit logs and active API keys return their existing JSON arrays with
`X-Page-Limit` and, when another page exists, `X-Next-Offset`. Keep filters and
limit while following the next offset. CORS exposes these headers. Ordering uses
a timestamp and UUID tie-breaker; concurrent mutations can shift offset pages.
This is bounded browsing, not a snapshot export. The console follows pages up
to 5,000 rows and displays an error if that limit is exceeded; SDK iterators
consume one page at a time. Single-object lineage/monitoring responses are not
catalog export interfaces.

## Storage growth and retention decisions

Offline history is **not partitioned**. The verified 100,000-row workload uses
an entity/feature/event-time covering index. It does not establish capacity for
millions of entities, multi-year history or production traffic. Track relation
and index bytes, disk headroom, dead tuples, autovacuum progress, query plans and
tail latency at the intended volume before deciding to partition.

There is no automatic deletion of offline events, inference observations, drift
runs, baselines, audit logs or job history. Retention remains explicit because
it changes historical reconstruction, monitoring evidence and recovery scope.
Choose a retention window and archive/backup policy with the dataset owner. A
blind `DELETE WHERE event_time < cutoff` can remove the last predecessor needed
for a later as-of observation; preserve a boundary snapshot per entity/feature
or restrict the documented historical query window accordingly. Keep baseline
and drift-run references intact when planning monitoring retention.

Use reviewed, small deletion batches during maintenance, with backup/restore
validation and vacuum monitoring. At higher measured volume, plan a separate
migration for time partitioning/archival and revisit primary-key uniqueness,
index size and pruning plans. The verified local workload does not justify an
automatic partition migration or a default destructive retention policy.
Expired Redis generations use `REDIS_TTL_SECONDS` (default 3,600); cache TTL does
not remove PostgreSQL history.

The streaming cursor uses SQLAlchemy's documented
[yield-per execution option](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#fetching-large-result-sets-with-yield-per).
Chunking bounds application allocations while maintaining one atomic write
transaction; it does not bound the source query's PostgreSQL working memory or
make long refreshes free of locks. Schedule refreshes against measured workload
and monitor read/write contention before raising the defaults.

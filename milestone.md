# Milestones and current scope

Reviewed 2026-11-25. The repository's P0, P1 and P2 acceptance work is implemented and locally verified. This is not a claim that an arbitrary production deployment meets an SLO or that packages have been published.

| Phase | Status | Delivered behavior |
| --- | --- | --- |
| P0 correctness and startup | Complete; commit `2af6fea` | Real registered JSON inference, transactional Redis consistency, atomic validation, database-enforced source SQL restrictions, managed persistent artifacts, fresh Compose initialization and deployment configuration. |
| P1 operational workflows | Complete; commit `1be82e2` | Recorded drift evidence, reliable scheduled slots/locking, deterministic fixtures, outcome/browser checks, scoped feature identities and event ordering, registry/admin transactions, trained tutorial, lineage controls, accessibility and recovery guidance. |
| P2 performance and release | Complete locally | Batched historical joins, lookup indexes, chunked materialization, bounded list APIs and consumers, reproducible benchmark results, pinned/audited dependencies, lint/format CI, supported runtime matrix, SDK lifecycle/errors/CLI, package validation and accurate documentation. |

See [P0](docs/P0_IMPLEMENTATION.md), [P1](docs/P1_IMPLEMENTATION.md), [P2](docs/P2_IMPLEMENTATION.md) and [performance evidence](docs/PERFORMANCE.md) for acceptance details.

## Release and deployment boundaries

The supported inference format is `featureops.linear.v1` for linear regression and binary logistic classification. Artifact storage also accepts opaque files, without executing them. PSI measurement is explicit; no automatic drift schedule is implemented. Offline history is indexed, not partitioned. Cron execution uses UTC at-most-once scheduled slots; crashes do not cause automatic replay.

CI definitions cover backend integration tests on Python 3.11/3.12/3.13, frontend checks on Node 24/26, SDK package build/install checks, dependency audits and fresh-stack browser/ML/persistence workflows. Local execution evidence is documented separately from remote CI status. No SDK upload or public deployment is included.

## Optional future work

- Kafka/Kinesis and warehouse/data-lake integrations beyond HTTP event push and PostgreSQL SELECT sources.
- Additional model runtimes with explicit isolation, signatures and dependency management.
- SSO, tenant/project isolation and scoped/expiring service credentials.
- Automatic drift schedules and operator-selected retention tools.
- Partitioning or archival after measurements at the deployment's actual volume justify migration.
- Automated package publishing and managed deployment after owner review of release artifacts.

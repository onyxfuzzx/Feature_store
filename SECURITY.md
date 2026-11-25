# Security reporting

Security fixes currently target the repository's 0.1.x development line. There is no published long-term support or incident response SLA.

Do not post exploit details or credentials in a public issue. Use the repository's GitHub Security tab to submit a private vulnerability report if enabled, or contact a maintainer privately using their repository profile contact method. Include affected revision, environment, reproduction steps and impact; redact passwords, API keys, tokens and private data. Maintainers will assess reports as availability permits.

Deployment operators own TLS, network access, account/credential rotation, backups and monitoring. See [operations](docs/OPERATIONS.md) and the [P0 configuration guide](docs/P0_IMPLEMENTATION.md). Dependency audits are point-in-time advisory checks and do not replace a security review.

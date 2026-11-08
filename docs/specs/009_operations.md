# Spec 009: operations

> Status: Draft · Implements: [NFR-004], [NFR-008], [NFR-001] · Decisions: [ADR-0009], [ADR-0011], [ADR-0012]
> Repos: arch-api, arch-web, arch-deploy · Last reviewed: 2026-11-08

## Summary

How the service runs and is observed: configuration, health, metrics, logs, traces, images
and deployment.

## Behaviour

- **SPEC-operations-01** `GET /healthz` returns `200 {"status":"ok"}` when the process is up. `GET /readyz` returns `200` only when the database is reachable and migrations are at the expected version, and `503` with the failing check otherwise. [NFR-004]
- **SPEC-operations-02** `GET /metrics` exposes Prometheus metrics: HTTP request count and duration by route and status, DB pool stats, import counts and durations, and impact query durations. It serves on a separate port (`METRICS_ADDR`, default `:9090`) that is not exposed through the ingress. [NFR-008] [NFR-001]
- **SPEC-operations-03** `arch-api` writes one JSON log line per request (`log/slog`: time, level, msg, method, route, status, duration_ms, trace_id, actor subject). Request bodies, tokens and attribute values are never logged. [NFR-008] [NFR-001]
- **SPEC-operations-04** When `OTEL_EXPORTER_OTLP_ENDPOINT` is set, the API exports traces over OTLP (gRPC or HTTP per `OTEL_EXPORTER_OTLP_PROTOCOL`), with spans for HTTP (gin) and SQL (pgx), and `service.name=arch-api`. When it is unset, tracing is off. `arch-web` sends a W3C `traceparent` header on API calls. [NFR-008]
- **SPEC-operations-05** All configuration comes from environment variables, documented in each repo's `.env.example` with dummy values. A missing required variable stops the process at startup with a message naming it. [NFR-001]
- **SPEC-operations-06** Each app repo builds a non-root, distroless (api) or nginx (web) image tagged with the git SHA, plus semver on release, and pushes it to GHCR. `arch-web` reads its runtime config from `/config.json`, so one image serves every environment. [NFR-004]
- **SPEC-operations-07** `arch-deploy` installs the api, the web app and a migration job (a Helm pre-upgrade hook running `arch-api migrate up`) on Kubernetes, with values for `dev` and `prod`. Secrets come from External Secrets (AWS Secrets Manager). [NFR-004]
- **SPEC-operations-08** The local stack (hub `dev/compose.yaml`) runs Postgres 16, Keycloak with the `arch` realm imported (seeded users `viewer@local`, `editor@local` and `admin@local`, and team `platform`), the api and the web app. Jaeger runs under the `tracing` profile. [NFR-008]

## Interfaces

- `arch-api` env: `DATABASE_URL`, `HTTP_ADDR`, `METRICS_ADDR`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_PROTOCOL`, `CORS_ORIGINS`.
- `arch-web` `/config.json`: `apiBaseUrl`, `oidcAuthority`, `oidcClientId`.
- `arch-api migrate up|status` subcommand.

## Data

- None owned.

## Non-functional

- [NFR-004]: 2 api replicas in prod, with a PodDisruptionBudget, and readiness gating traffic.

## Open questions

- Which OTLP backend does the organisation use in dev and prod (Tempo, Jaeger, a vendor)? — khajonpot

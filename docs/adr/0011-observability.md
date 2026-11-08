# ADR-0011: Observability

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [NFR-008]

## Context

[NFR-008] asks for logs, health, metrics and traces. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **slog JSON logs + Prometheus metrics + OpenTelemetry traces over OTLP**.
2. **A vendor agent** — ties the tool to one vendor.

## Decision

`arch-api` logs JSON with `log/slog`; exposes `/healthz`, `/readyz` and Prometheus `/metrics`;
exports OpenTelemetry traces over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (off when unset),
with OTel middleware for gin and pgx. `arch-web` sends a `traceparent` header on API calls. Locally
Jaeger runs under the compose `tracing` profile.

## Consequences

- Logs never contain tokens or model data marked sensitive ([NFR-001]).

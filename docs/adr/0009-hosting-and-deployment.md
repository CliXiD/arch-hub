# ADR-0009: Hosting and deployment

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [NFR-001], [NFR-004]

## Context

Self-hosted inside the organisation, target AWS EKS with RDS Postgres. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **Docker images + Helm chart on Kubernetes (EKS), RDS Postgres** — fits the target.
2. **ECS or VMs** — not the organisation's target.

## Decision

Each app repo builds a Docker image pushed to GHCR. `arch-deploy` holds the Helm chart (api, web
served by nginx, optional Keycloak config) and values per environment: `dev`, `prod`. Local dev
uses Docker Compose (Postgres 16, Keycloak with the seeded realm, api, web, and Jaeger under the
`tracing` profile) in the hub's `dev/`. Deploys are a person's call.

## Consequences

- `arch-deploy` is an infra repo (`implies: infra`), never auto-merged.
- Migrations run as a Helm pre-upgrade job using the api image.

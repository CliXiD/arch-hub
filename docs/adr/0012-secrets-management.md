# ADR-0012: Secrets management

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [NFR-001], [NFR-002]

## Context

Apps need DB credentials and OIDC client secrets; the model itself must never hold secrets
([NFR-002]). Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **`.env` locally (examples committed), External Secrets Operator from AWS Secrets Manager in prod**.
2. **Sealed secrets in git** — key management in the cluster, secrets in git history.

## Decision

Option 1. Each app repo commits `.env.example` with dummy values; real `.env` files are git-ignored.
In Kubernetes, secrets come from AWS Secrets Manager through External Secrets Operator.

## Consequences

- No secret ever appears in a repo, the hub, logs or the model.

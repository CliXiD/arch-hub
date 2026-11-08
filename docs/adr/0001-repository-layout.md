# ADR-0001: Repository layout

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-011], [NFR-001]

## Context

The product is an internal web tool with a backend, a single-page frontend and its deployment
config [S-001]. The existing `CliXiD/arch-diagram` repo was empty (README only). Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **One monorepo** (`apps/api`, `apps/web`, deploy) — one PR per change and no cross-repo
   contracts, but it mixes Go and Node toolchains and CI in one repo.
2. **Four repos including a shared `arch-model`** (schema + types package) — the model could be
   shared, but the backend is Go and the frontend is TypeScript, so a shared code package adds a
   publishing step for little gain.
3. **Three repos: `arch-api`, `arch-web`, `arch-deploy`** — each repo has one toolchain; the
   contract between them is the OpenAPI spec that `arch-api` generates.

## Decision

Three private repos under `CliXiD`, each with base `main`:

| key | repo | role | merge order |
|---|---|---|---|
| `arch-api` | `CliXiD/arch-api` | Go REST API, graph storage, impact queries, YAML schema and import/export, `arch` CLI, audit log; owns the DB schema | 1 |
| `arch-web` | `CliXiD/arch-web` | React SPA: landscape, focus and impact views, editors, admin | 2 |
| `arch-deploy` | `CliXiD/arch-deploy` | Dockerfiles, Helm chart, Keycloak realm export | 3 |

`arch-diagram` is removed from the hub (it stays on GitHub; deleting or archiving it is the
owner's call). There is no `arch-model` repo: the YAML JSON Schema and the CLI live in
`arch-api` ([ADR-0006]).

## Consequences

- `arch-api` changes first; `arch-web` consumes `arch-api/api/openapi.yaml` ([ADR-0003]).
- A feature touching API and UI is two PRs on the same branch name, merged api first.
- `arch-deploy` follows image and config changes in the other two.

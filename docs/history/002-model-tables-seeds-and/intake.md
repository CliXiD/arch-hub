DECISION: ACCEPT
RISK: high
SURFACES: security
REPOS: arch-api, arch-web
RESCOPED: no

## Summary
- Accepted as written: model tables and seed migrations, sqlc queries, the seven read endpoints under `/api/v1`, and `arch-api seed --sample`, all in `arch-api`; `arch-web` only regenerates `src/api/schema.d.ts`. `arch-deploy` is untouched.
- The issue repeats [SPEC-model-01]..[08], the Interfaces and Data of `002_model.md` and [ADR-0004] faithfully; I found no contradiction with the documents. The blocker #3 (walking skeleton) is merged in both repos, so `migrate`, the auth middleware and the default-deny registry this slice builds on exist.
- Two things the spec writer must pin down because the documents give only examples: the full default `allowed` kind pairs for the six edge types (they must admit the sample graph, including network → network for `routes_via`), and a stable sort key behind the opaque cursor. I give the sensible reading below.
- Per [ADR-0014] the `arch_app` grants arrive with the write slice, so these migrations create tables only and `DATABASE_URL` stays on the owner; no new env var, hence no `arch-deploy` change.
- Risk is high: the first real DB migrations (protected path, seeded in prod too) and new endpoints that return model attribute values ([NFR-001]). No research needed.

## Scope
Build the slice exactly as the issue's Behaviour, Decisions and Contract describe. Everything below is read as relative to `/api/v1`, minimum role `viewer` ([SPEC-identity-access-04]), RFC 9457 errors.

**arch-api**
- New goose migrations (never editing `00001_baseline.sql`): `node_types`, `edge_types`, `teams`, `environments`, `nodes` (PK `(environment, id)`, `id` CHECK `^[a-z0-9][a-z0-9-]{1,62}$`, FKs to `node_types`, `teams`, `environments`, `version int` starting at 1), `edges` (`uid uuid`, unique `(environment, type, from_id, to_id)`, composite FKs `(environment, from_id)` and `(environment, to_id)` → `nodes`, so both ends are in the same environment, [SPEC-model-07]). Indexes to support the list filters and `GET /graph` at 2,000 nodes / 10,000 edges ([NFR-005]). No grants to `arch_app` in this slice ([ADR-0014] assigns them to the write slice); no `change_log` table.
- Seed migration (runs in every environment, Decision 1): the 14 node types and 6 edge types of [SPEC-model-02] with `builtin = true`; `calls` with `protocol` (enum `http`, `https`, `grpc`, `tcp`, `amqp`, `kafka`, `other`) and `port` (number 1–65535) per [SPEC-model-03]; environments `dev` (sort 1), `uat` (2), `prod` (3). No teams. Default `allowed` pairs, since the spec gives only examples — the spec writer should use this reading unless the documents say otherwise: `runs_on` application → infrastructure only (acceptance criterion); `stores_data_in` application → infrastructure; `calls` application → application | external; `depends_on` application → application | infrastructure | external; `routes_via` application | network → network (needed for `vpc-prod → landing-zone → direct-connect`); `owned_by` application | infrastructure | network | external → team.
- sqlc set up in the repo (config, queries, generated code regenerated, never hand-edited), using the existing pgx pool.
- Endpoints, shapes exactly as the issue's Contract: `GET /types` (grouped `node_types` / `edge_types`, not paginated), `GET /teams` and `GET /environments` (whole list in `items`, ordered by name resp. `sort`, not paginated), `GET /nodes` and `GET /edges` (filters as listed, `q` case-insensitive on id and name, `limit` default 100 max 500, opaque `cursor`, `{ items, next_cursor }`; a bad `limit`, `cursor` or unknown `environment`/`kind` → `422 /problems/validation`), `GET /nodes/{environment}/{id}` with `ETag: "<version>"` and `404 /problems/not-found`, `GET /graph?environment=` (required; compact nodes without `attributes`, edges with theirs; gzip when `Accept-Encoding` allows). Cursor paging needs a stable total order — `(environment, id)` for nodes and `(environment, type, from_id, to_id)` for edges is the obvious choice. Only the single-node read carries `ETag` in this slice: the Contract has no single-edge read yet.
- Every new operation goes through the existing `register()` with `minRole viewer`, so the default-deny test covers it. Query parameters reach SQL only as sqlc parameters. Attribute values are never logged (the request logger already excludes query strings and bodies; keep problem `detail` free of them).
- `arch-api seed --sample` (new subcommand next to `serve` and `migrate`, using `DATABASE_URL`): in one transaction, refuses with a non-zero exit and no writes when `nodes` has any row; otherwise creates teams `platform` and `core` and the sample graph of the Contract in `prod` (7 nodes, 6 edges, `source` = `import`, `version` 1; `calls` attributes `{"protocol":"https","port":443}`). Document it in the README and `.env.example` needs no change.
- Integration test behind `//go:build integration` with testcontainers (Postgres 16): migrate up, load 2,000 nodes and 10,000 edges, assert `GET /graph` under 1 s and the seed refusal. It stays out of the gate ([ADR-0010]); wiring it into CI touches the protected `.github/*` path and will be escalated.
- `make openapi` regenerated; `make openapi-check` passes.

**arch-web**
- Regenerate `src/api/schema.d.ts` with `pnpm gen:api` from the merged `api/openapi.yaml`; `pnpm run typecheck` passes. No screen changes.

**Left out** (as the issue says): write endpoints, `change_log`, secret detection, `If-Match` handling, neighbourhood and impact queries, admin CRUD of types/teams/environments, `arch_app` grants, web screens, any `arch-deploy` change. Docs impact for the approver: `009_operations.md` Interfaces should gain `arch-api seed --sample`; `002_model.md` should record the default `allowed` pairs once the spec fixes them.

**Merge order:** `arch-api` first, then regenerate `schema.d.ts` in `arch-web`.

## Why
The documents already answer the design: `docs/specs/002_model.md` gives the same endpoints, shapes, pagination rule, ETag rule, graph compaction and tables the issue lists, and [ADR-0004] fixes PostgreSQL 16 + pgx/sqlc + goose; the issue adds only the `seed --sample` developer tool and the sample graph. The skeleton merged from job 001 (`docs/history/001-walking-skeleton-sign-in/build.md`: `cmd/arch-api` subcommand dispatch, `internal/db` with pgxpool and goose, `internal/httpapi/register()` with `minRole` and the registry test, `make openapi`/`openapi-check`) provides every hook this slice needs, and `factory/checks/arch-api.sh` keeps `//go:build integration` tests out of the gate as [ADR-0010] requires. The local `repos/arch-api` checkout is behind the merged `main`, so I judged the code from the 001 build record rather than the files; the builder works from a fresh worktree. Risk is high because of the protected `migrations/*` path and seeds that run in prod ([Factory notes], "DB migrations"); the security surface is the new read routes exposing attribute values ([NFR-001]) and user-supplied filters reaching queries.

## Questions
None.

## Research
None.

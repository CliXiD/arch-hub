# Write API for nodes, edges, teams and environments with change log

> Issue #5: Write API for nodes, edges, teams and environments with change log

## Summary
- `arch-api` gets the write side of the model: create, update and delete for nodes and edges (editor, team-scoped) and for teams and environments (admin), as specified in [SPEC-editing-history-06], [SPEC-model-03]..[SPEC-model-10], [SPEC-identity-access-05] and the Interfaces of `008_admin.md` (pulled forward, issue Decision 1).
- Every successful write records exactly one append-only `change_log` row per entity in the same transaction ([ADR-0005], [NFR-003]); a new history endpoint returns a node's rows and its edges' rows, newest first ([SPEC-editing-history-07]).
- New goose migrations add `change_log` with a trigger that rejects UPDATE, DELETE and TRUNCATE, and grant the runtime role `arch_app` DML on the model tables but only SELECT and INSERT on `change_log` ([ADR-0014], [SPEC-editing-history-08]). `MIGRATE_DATABASE_URL` already exists in config; this job documents and tests the split end to end.
- Optimistic locking is mandatory on node and edge PATCH/DELETE (`If-Match`, `412`/`428`); attributes are checked against the type schema and for secrets without echoing values ([NFR-001], [NFR-002]).
- `arch-web` only regenerates `src/api/schema.d.ts` from the new `api/openapi.yaml`; no screens change.

## Context

### arch-api
- **Routes and access.** `arch-api:internal/httpapi/api.go` holds `register()` (the only way to add an operation; records `minRole` in metadata, adds bearer security and 401/403/413/503), `accessMiddleware` (puts `auth.Principal` in the context), `newProblem` (Huma's `huma.NewError`: sets `type` for 404/422 and clears every `errors[].value`) and the problem type constants. `arch-api:internal/httpapi/registry_test.go` fails when an operation lacks a minimum role.
- **Model reads.** `arch-api:internal/httpapi/routes_model.go` registers the read routes against the `Model` interface and maps errors with `modelFailure` (404, 422 from `*model.ValidationError{Location, Message}`, else 500 logged with `errorClass` only). `GET /api/v1/nodes/{environment}/{id}` already returns `ETag: "<version>"` via `strconv.Quote(strconv.Itoa(version))`.
- **Service.** `arch-api:internal/model/service.go` (`Service` over `pgxpool.Pool` and `dbq.Queries`, `WithTx` used in `Graph`), `types.go` (`Node`, `Edge`, `Team`, `Environment`, `NodeType`, `EdgeType`, `KindPair`, pages with `next_cursor`), `cursor.go` (`encodeCursor`/`decodeCursor`, opaque base64 JSON), `errors.go` (`ErrNotFound`, `ValidationError`). `arch-api:internal/model/seed.go` writes the sample graph (dev only).
- **SQL.** `arch-api:internal/db/queries/model.sql` and `seed.sql`, generated into `arch-api:internal/db/dbq` by `make sqlc` (never hand-edited). Schema in `arch-api:migrations/00002_model.sql`: six tables `environments`, `teams`, `node_types`, `edge_types`, `nodes` (PK `(environment, id)`, `version int`), `edges` (`uid uuid`, unique `(environment, type, from_id, to_id)`, FKs to nodes without cascade, indexes on `(environment, from_id)` and `(environment, to_id)`); slug CHECKs on ids. `00003_model_seed.sql` seeds vocabulary and `dev`/`uat`/`prod`; edge type schemas hold `type`, `enum`, `minimum`, `maximum` (e.g. `calls.port`), node type schemas are `{"type":"object","properties":{}}`. All three migrations are protected.
- **Identity.** `arch-api:internal/auth/principal.go`: `Principal{Subject, Name, Email, Roles, Teams, ActorKind}`; `PrincipalFromClaims` sets a service account (`client_id == azp`) to `Subject = Name = client id`; for users `Name` is the `name` claim, falling back to `preferred_username`. `Claims.PreferredUsername` is parsed but not kept on `Principal`.
- **Config and commands.** `arch-api:internal/config/config.go` `LoadMigrate` already reads `MIGRATE_DATABASE_URL` and falls back to `DATABASE_URL`; `LoadServe`/`LoadSeed` read `DATABASE_URL` (tested in `config_test.go`, `cmd/arch-api/main_test.go`). `.env.example` already lists `MIGRATE_DATABASE_URL`. `arch-api:internal/db/migrate.go` runs goose as the migrate URL; `arch-api:internal/db/db.go` `VersionReader` reads `goose_db_version` for readiness on the runtime pool.
- **Wiring.** `arch-api:internal/httpapi/engine.go` `Deps{Auth, Ready, Model, Logger, Metrics, CORSOrigins, Tracing}`; `arch-api:internal/httpapi/serve.go` builds `model.NewService(pool)` on `DATABASE_URL`. Request logs carry no bodies, headers or query strings (`internal/observability/logging.go`); `otelpgx` traces queries without arguments.
- **Tests.** Unit tests in `internal/httpapi/*_test.go` use `newTestServer`, signed test tokens (`internal/auth/authtest`) and a `fakeModel`. `arch-api:cmd/arch-api/integration_test.go` (`//go:build integration`) starts `postgres:16` with testcontainers as user `arch`, runs `db.Migrate`, and exercises the read API.
- **Docs.** `arch-api:README.md` documents config, endpoints, problems, paging and the layout.

### arch-web
- `arch-web:src/api/schema.d.ts` is generated by `pnpm gen:api` (`openapi-typescript ${ARCH_API_OPENAPI:-../arch-api/api/openapi.yaml}`); in this job's worktrees the default path resolves to the `arch-api` worktree. `arch-web:src/api/client.ts` and `me.ts` consume it.

### Hub
- `dev/postgres/init/02-arch-app.sql` creates role `arch_app` (LOGIN, CONNECT, USAGE on `public`); `dev/env/arch-api.env` keeps `DATABASE_URL` on `arch` until this job merges.

## Contract

The interface between `arch-api` and `arch-web` is `arch-api:api/openapi.yaml`, regenerated from the Huma types below ([ADR-0003], [ADR-0007]). All paths are under `/api/v1`, bearer token required, errors are RFC 9457 `application/problem+json` using Huma's `ErrorModel` (`type`, `title`, `status`, `detail`, `errors: [{location, message}]`, `value` always absent).

### Shapes (existing, unchanged)
`Node`, `Edge`, `Team`, `Environment` as in `arch-api:internal/model/types.go` and served by the read endpoints today.

### Node writes (minimum role `editor`)
- `POST /nodes` body
  ```json
  { "environment": "prod", "id": "payments-api", "type": "service", "name": "Payments API",
    "description": "", "owner": "platform", "tags": ["pci"], "attributes": {} }
  ```
  `description`, `tags`, `attributes` optional (defaults `""`, `[]`, `{}`); `id` pattern `^[a-z0-9][a-z0-9-]{1,62}$`; no other properties allowed. → `201 Node`, header `ETag: "1"`, `source: "ui"`.
- `PATCH /nodes/{environment}/{id}`, header `If-Match: "<version>"` required, body any subset of `{ "name", "description", "owner", "tags", "attributes" }`; each present field replaces the stored value (`tags` and `attributes` are replaced whole, not merged). Any other property (`id`, `type`, `environment`, ...) → `422 /problems/validation` at `body.<name>`. → `200 Node` with the new `ETag`. A no-op returns `200` with the unchanged node and `ETag`.
- `DELETE /nodes/{environment}/{id}`, `If-Match` required → `204`; deletes every edge with `from` or `to` equal to the node in its environment.

### Edge writes (minimum role `editor`)
- `POST /edges` body `{ "environment": "prod", "type": "calls", "from": "payments-api", "to": "ledger", "attributes": { "protocol": "https", "port": 443 } }` (`attributes` optional) → `201 Edge`, `ETag: "1"`.
- `PATCH /edges/{uid}` (`uid` format uuid), `If-Match` required, body `{ "attributes": {...} }` (required, replaces whole) → `200 Edge` + `ETag`.
- `DELETE /edges/{uid}`, `If-Match` required → `204`.

### Team and environment writes (minimum role `admin`, no `If-Match`)
- `POST /teams` `{ "id": "<slug>", "name": "..." }` → `201 Team`; `PATCH /teams/{id}` `{ "name": "..." }` → `200 Team`; `DELETE /teams/{id}` → `204`.
- `POST /environments` `{ "id": "<slug>", "name": "...", "sort": 4 }` → `201 Environment`; `PATCH /environments/{id}` `{ "name"?, "sort"? }` → `200 Environment`; `DELETE /environments/{id}` → `204`.

### History (minimum role `viewer`)
- `GET /history?entity=node&environment=prod&id=payments-api&limit=50&cursor=...`; `entity` required, enum `node` only in this slice; `environment`, `id` required; `limit` default 50, 1..500; `cursor` opaque.
  ```json
  { "items": [ { "id": 42, "at": "2026-11-09T10:00:00.123456Z", "actor": "f3c1...", "actor_name": "editor",
                 "actor_kind": "user", "source": "ui", "entity": "edge", "entity_key": "6b1f...-uuid",
                 "action": "delete", "before": { "uid": "...", "from": "payments-api", "to": "ledger", ... }, "after": null } ],
    "next_cursor": null }
  ```
  Order `(at desc, id desc)`. Includes rows of deleted nodes and edges. An unknown node gives `200` with empty `items`.

### Errors
| status | type | when |
|---|---|---|
| 401 | `/problems/unauthenticated` | no/invalid token (existing) |
| 403 | `/problems/forbidden` | role too low (existing); editor lacks rights — `detail` = `node is owned by team <team-id>` (for edges, the source node's owner; for owner changes, the team the caller lacks) |
| 404 | `/problems/not-found` | node, edge, team or environment in the path does not exist |
| 409 | `/problems/conflict` | duplicate node `(environment, id)`, duplicate edge `(environment, type, from, to)`, duplicate team/environment id, duplicate environment `sort` |
| 409 | `/problems/in-use` | delete of a team owning nodes or an environment holding nodes; body adds integer member `count` (number of nodes) |
| 412 | `/problems/stale` | `If-Match` does not equal `"<current version>"` (including `*`, weak or malformed values) |
| 422 | `/problems/validation` | request schema, unknown `type`/`owner`/`environment`/`from`/`to`, attribute schema, kind pair; one `errors[]` entry per bad field, `location` like `body.attributes.port` |
| 422 | `/problems/secret-detected` | secret check failed; `errors[]` entries `{location: "body.attributes.db_password", message: "looks like a secret"}`; no value anywhere |
| 428 | `/problems/precondition-required` | `If-Match` missing on node/edge PATCH or DELETE |

The issue's `path` is Huma's `location`; there is one 422 shape ([ADR-0003]).

### Schema
- New table `change_log` ([SPEC-editing-history-06] Data):
  `id bigserial PRIMARY KEY`, `at timestamptz NOT NULL DEFAULT now()`, `actor text NOT NULL`, `actor_name text NOT NULL`, `actor_kind text NOT NULL CHECK IN ('user','service')`, `source text NOT NULL CHECK IN ('ui','yaml','discovery','import')`, `entity text NOT NULL CHECK IN ('node','edge','type','team','environment')`, `entity_key text NOT NULL`, `action text NOT NULL CHECK IN ('create','update','delete')`, `before jsonb NULL`, `after jsonb NULL`, `CHECK (before IS NOT NULL OR after IS NOT NULL)`.
- `entity_key`: node `<environment>/<id>`, edge `<uid>`, team `<id>`, environment `<id>`.
- `before`/`after`: the entity's API JSON (`Node`, `Edge`, `Team`, `Environment`); `before` null on create, `after` null on delete.
- Indexes: `(entity, entity_key, at DESC, id DESC)`; two partial expression indexes for a node's edges, `WHERE entity = 'edge'`: `((coalesce(after, before)->>'environment'), (coalesce(after, before)->>'from'), at DESC, id DESC)` and the same with `'to'`. (An edge's `environment`, `from`, `to` are immutable, so `coalesce(after, before)` is stable.)
- Trigger function `change_log_reject()` raising an exception; `BEFORE UPDATE OR DELETE ... FOR EACH ROW` and `BEFORE TRUNCATE ... FOR EACH STATEMENT` triggers on `change_log`.
- Grants to role `arch_app`: `USAGE ON SCHEMA public`; `SELECT, INSERT, UPDATE, DELETE` on `environments`, `teams`, `node_types`, `edge_types`, `nodes`, `edges`; `SELECT, INSERT` on `change_log`; `USAGE, SELECT` on `change_log_id_seq`; `SELECT` on `goose_db_version` (readiness). Only `arch-api` owns schema ([ADR-0004]); repos.json `rules` is empty.

### Env vars
- `MIGRATE_DATABASE_URL` (optional, default `DATABASE_URL`), read by `config.LoadMigrate` for `arch-api migrate`; already implemented. `DATABASE_URL` is the runtime role for `serve` and `seed`. No new variable.

### Compatibility
- Only additions: new operations, new problem types, new table. Existing read operations and shapes are unchanged, so the deployed `arch-web` keeps working before regeneration.
- Deploying the migrations requires role `arch_app` to exist first (the migration fails with "role arch_app does not exist" otherwise). A server still on the owner `DATABASE_URL` keeps working; switching it to `arch_app` is the hub/deploy follow-up.

## Requirements

### arch-api

**Migrations**
1. Add new goose files only, never editing `00001`-`00003`: `migrations/00004_change_log.sql` (table, CHECKs, indexes, trigger function and triggers per Contract → Schema) and `migrations/00005_app_role_grants.sql` (the grants per Contract → Schema). Each has a `-- +goose Down` that reverses it (drop triggers, function, table; revoke grants). Use `-- +goose StatementBegin/End` around the plpgsql function.
2. Run `make sqlc` after adding queries; commit `internal/db/dbq` unedited.

**Identity**
3. Add `Username string` to `auth.Principal`: `preferred_username` for users, the client id for service accounts (`client_id == azp`). Existing fields and their values do not change. Extend `principal_test.go` table cases.

**Service layer (`internal/model`)**
4. New `model.Actor{Subject, Username, Kind string; Admin bool; Teams []string}` passed by handlers (built from `Principal`: `Admin = p.Has(auth.RoleAdmin)`); `internal/model` does not import `internal/auth`.
5. New write methods on `*model.Service` (e.g. `internal/model/write.go`): `CreateNode`, `UpdateNode`, `DeleteNode`, `CreateEdge`, `UpdateEdge`, `DeleteEdge`, `CreateTeam`, `UpdateTeam`, `DeleteTeam`, `CreateEnvironment`, `UpdateEnvironment`, `DeleteEnvironment`, each running in one `pgx` transaction (`s.q.WithTx(tx)`, as `Graph` does) that also inserts the `change_log` row(s) via a single helper; on any error the transaction rolls back and no row remains.
6. Node/edge update and delete: `SELECT ... FOR UPDATE` the row, then check permission, then compare `version` with the `If-Match` version (`ErrStale`), then validate, then write `version = version + 1`, `updated_at = now()`, `source = 'ui'`. If the patched entity equals the stored one (name, description, owner, tags, attributes compared as JSON values), commit nothing: no version bump, no `change_log` row, return the current entity.
7. Permissions ([SPEC-identity-access-05]): admin may write anything; otherwise a node write needs `owner ∈ Actor.Teams`; an owner change needs both the old and the new team; an edge write needs rights on its `from` node's owner. Failure returns a typed `model.ForbiddenError{Team}`. Edges from other teams' nodes are deleted by a node delete without any further check (Decision 5).
8. Node delete: lock the node, check permission and version, `SELECT ... FOR UPDATE` every edge with `(environment, from_id)` or `(environment, to_id)` equal to the node, delete each and write one `change_log` row per edge (`action delete`, `after null`), then delete the node and write its row. One transaction.
9. Reference checks → `ValidationError`: unknown `type` (`body.type`), unknown `owner` (`body.owner`), unknown `environment` (`body.environment`), `from`/`to` not a node in the edge's `environment` (`body.from`/`body.to`; this is how cross-environment edges are rejected, [SPEC-model-07]), and a kind pair not in the edge type's `allowed` (`body.to`, message `edge type <t> does not allow <fromKind> → <toKind>`, [SPEC-model-04]). Unique violations (SQLSTATE `23505`) → `ErrConflict`; FK violation `23503` on an edge insert → the same `body.from`/`body.to` validation error.
10. Attribute validation ([SPEC-model-03]) in a new hand-written `internal/model/validate.go` (no new dependency): supports `type` `string|number|boolean|array` (array `items.type: string`), `enum`, `minimum`, `maximum`, `required`, and `additionalProperties: false` when a schema sets it. Attributes not declared in `properties` are allowed, but every attribute value must be a string, number, boolean or array of strings; anything else (object, null, mixed array) fails with `unsupported attribute type`. All failures are collected and returned together, each with `location` `body.attributes.<name>` and a fixed message that never includes the value.
11. Secret check ([SPEC-model-10]) in a new `internal/model/secrets.go`, run after attribute validation passes, on every node and edge create/update: attribute names matching `(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)`; string values (including array elements, location `body.attributes.<name>[<i>]`) that contain a URL with userinfo `scheme://user:pass@`, a PEM header `-----BEGIN [A-Z0-9 ]+-----`, or `AKIA[0-9A-Z]{16}`. Returns `model.SecretError{Locations []string}`; the error, its `Error()` text and every log line never contain the value.
12. Team/environment delete: count nodes with that `owner` / `environment`; non-zero → `model.InUseError{Count}`, nothing deleted, no row.
13. `History(ctx, environment, id, limit, cursor)`: one query whose `WHERE` is `(entity='node' AND entity_key = env||'/'||id) OR (entity='edge' AND coalesce(after,before)->>'environment' = env AND (coalesce(after,before)->>'from' = id OR coalesce(after,before)->>'to' = id))`, keyset `(at, id) < (cursor)`, `ORDER BY at DESC, id DESC`, `LIMIT limit+1`, using the Contract's indexes (so a self-loop edge appears once). Cursor via the existing `encodeCursor(at RFC3339Nano, id)` / `decodeCursor(.., 2)`; a bad cursor gives `query.cursor` validation error.

**HTTP layer (`internal/httpapi`)**
14. New problem constants `ProblemConflict`, `ProblemInUse`, `ProblemStale`, `ProblemPreconditionRequired`, `ProblemSecretDetected`, set on the problems the handlers return (extend `newProblem`/the failure mapper; keep `value` cleared). The in-use problem is Huma's error model plus an integer `count` member, documented as the 409 schema of the two delete operations.
15. Register every new operation through `register()` with the Contract's minimum role, its `Errors` (404/409/412/422/428 as applicable) so they appear in `openapi.yaml`, and `ETag` response headers on node/edge create and PATCH. Handlers stay thin: parse, build `Actor` from `auth.PrincipalFrom`, call the service, map errors. Missing `If-Match` → `428` before the service is called.
16. Add the write methods and `History` behind interfaces in `Deps` (extend `Model` with `History`; new `Writer` interface for the writes), both implemented by `*model.Service` and wired in `serve.go`. A 500 logs only the operation and `errorClass`, never values.
17. Order of checks for PATCH/DELETE: request schema (422) → `If-Match` present (428) → entity exists (404) → permission (403) → version (412) → attribute/reference validation (422) → secret check (422) → write.

**Tests (unit, in the gate)**
18. Table-driven tests in `internal/model` for `validate.go` and `secrets.go`, and in `internal/httpapi` (fake writer) for routing, roles, problem types, `ETag`, 428/412 and that no response body or captured log contains a secret value. Extend `fakeModel` for `History`.

**Integration test (`//go:build integration`, out of the gate, [ADR-0010])**
19. In `cmd/arch-api/integration_test.go` (or a new `_test.go` in the same package): create role `arch_app` with a password before `db.Migrate` (as the container's `arch` user); build the API's pool as `arch_app` so the existing read assertions and all new write assertions run as the runtime role; cover: `UPDATE change_log` and `DELETE FROM change_log` as `arch_app` fail with SQLSTATE `42501`; as `arch` the trigger rejects `UPDATE`, `DELETE` and `TRUNCATE`; `db.VersionReader` works as `arch_app`; the cascade delete gives three rows; a failed write gives none; a no-op PATCH gives none and keeps `version`; history order and content.

**Docs**
20. `README.md`: add the write and history endpoints to the Endpoints table; a section on `If-Match`/`ETag`, the new problems (with `count`), permissions, the secret rule (values never echoed); the database roles (migrations as owner via `MIGRATE_DATABASE_URL`, server as `arch_app`, role must exist before `migrate up`, future migrations must grant new tables to `arch_app`); `internal/model` layout line; add `specs/003_editing-history.md` and `adr/0005` to Documents. Update the intro paragraph to mention the write slice.
21. `make openapi`; commit `api/openapi.yaml` regenerated.

### arch-web
22. After `arch-api`'s `api/openapi.yaml` is final, run `pnpm gen:api` in the worktree (default path reads the `arch-api` worktree) and commit `src/api/schema.d.ts` unedited. No other file changes.

## Acceptance criteria

Unit-level criteria run with `cd <arch-api worktree> && go test -count=1 ./...`; integration ones with `go test -tags integration -count=1 ./cmd/arch-api/...` (podman/docker). Local-stack criteria use `dev/bin/stack reset && dev/bin/stack up`, `migrate up` as `arch`, `seed --sample`, then `serve` with `DATABASE_URL=postgres://arch_app:arch_app@localhost:5432/arch?sslmode=disable`, tokens from realm `arch`.

1. [arch-api] `ls migrations/` shows new `00004_*.sql` and `00005_*.sql`; `git diff origin/main -- migrations/00001_baseline.sql migrations/00002_model.sql migrations/00003_model_seed.sql` is empty.
2. [arch-api] `editor` (team `platform`) `POST /api/v1/nodes` `{environment: prod, id: payments-api, type: service, name: Payments, owner: platform}` → `201`, `ETag: "1"`, `source: "ui"`; the same with `owner: core` → `403`, `type /problems/forbidden`, `detail` contains `core`. A `viewer` token → `403`. (Integration test and local stack.)
3. [arch-api] `editor` `POST /api/v1/edges` from a `platform` node to a `core` node (allowed pair) → `201`; from a `core` node → `403` naming `core`; `admin` gets `201` for both.
4. [arch-api] Table-driven validation tests return `422 /problems/validation` with the stated location: attribute value of an unsupported type (object) → `body.attributes.<name>`; `calls` edge `port: 70000` → `body.attributes.port`; `runs_on` application → network → `body.to`; `to` existing only in another environment → `body.to`; id `Bad_Slug` → `body.id`; PATCH with `id`/`type`/`environment` → `body.id`/`body.type`/`body.environment`. Duplicate node id and duplicate edge → `409 /problems/conflict`.
5. [arch-api] Table-driven secret tests: attribute names `password`, `API_KEY`, `privateKey`; values `postgres://u:p@h/db`, a PEM block, `AKIA` + 16 uppercase chars → `422 /problems/secret-detected` with `errors[].location` `body.attributes.<name>`; the response body and a captured logger output contain neither the value nor any 6-character substring of it.
6. [arch-api] PATCH and DELETE of a node and an edge with `If-Match: "999"` → `412 /problems/stale`; with `If-Match: *` → `412`; without `If-Match` → `428 /problems/precondition-required`; PATCH with the right version → `200` and `ETag` one higher.
7. [arch-api] Integration: deleting a node with one outgoing edge and one incoming edge from another team's node → `204`, both edges gone, exactly three new `change_log` rows (one `node`, two `edge`, all `action delete`, same `at`).
8. [arch-api] Integration: a create rejected with `422` leaves the `change_log` row count unchanged; a PATCH with identical values → `200`, `version` unchanged, no new row.
9. [arch-api] Integration: `GET /api/v1/history?entity=node&environment=prod&id=payments-api` after create, update, edge create and edge delete returns those rows newest first with `before`/`after`, `actor_kind: "user"`, `actor_name: "editor"`-style username, `source: "ui"`; with `limit=1` `next_cursor` is non-null and following it returns the next row; `cursor=garbage` → `422` at `query.cursor`.
10. [arch-api] A write with a service-account token (`client_id == azp`, e.g. `arch-ci-platform`) records `actor_kind: "service"` and `actor` = `actor_name` = the client id (unit test on the handler-to-`Actor` mapping plus the integration test).
11. [arch-api] `admin` `DELETE /api/v1/teams/platform` while it owns nodes → `409 /problems/in-use` with `count` equal to the number of owned nodes; `POST /api/v1/environments {id: sandbox, name: Sandbox, sort: 4}` → `201`, then `DELETE /api/v1/environments/sandbox` → `204`; each successful team/environment write adds one `change_log` row (entity `team`/`environment`); `editor` on any team/environment write → `403`.
12. [arch-api] Integration: as `arch_app`, `UPDATE change_log SET actor='x'` and `DELETE FROM change_log` fail with SQLSTATE `42501`; as `arch`, `UPDATE`, `DELETE` and `TRUNCATE change_log` each fail with the trigger's exception.
13. [arch-api] `go test ./internal/config/... ./cmd/arch-api/...` covers `migrate` using `MIGRATE_DATABASE_URL` when set and `serve`/`seed` using `DATABASE_URL` (existing cases stay green); the integration test migrates as `arch` and serves as `arch_app`.
14. [arch-api] Local stack: after `dev/bin/stack reset`, `MIGRATE_DATABASE_URL=...arch:arch... go run ./cmd/arch-api migrate up` applies through `00005`; `serve` with `DATABASE_URL` as `arch_app` answers `/readyz` `200` and criteria 2, 3, 6, 9 and 11 hold against it.
15. [arch-api] `internal/httpapi/registry_test.go` passes with every new operation registered; `grep -n "history\|/edges/{uid}\|/teams/{id}\|/environments/{id}\|precondition-required\|secret-detected\|in-use" api/openapi.yaml` finds each; `make openapi-check` passes.
16. [arch-api] `README.md` documents the write and history endpoints, `If-Match`, the new problem types, `MIGRATE_DATABASE_URL`, and that role `arch_app` must exist before `migrate up`.
17. [arch-web] `git diff --stat origin/main` lists only `src/api/schema.d.ts`; `pnpm gen:api && git diff --exit-code src/api/schema.d.ts` is clean (regenerated, not hand-edited) and `grep -n '"/api/v1/history"' src/api/schema.d.ts` matches; `pnpm run typecheck` passes.

## Merge and deploy order
1. `arch-api` first (`merge_order`): it owns the schema and the contract. Before its migrations run in any environment, role `arch_app` must exist (local: hub init script; prod: deploy slice).
2. `arch-web` second: `schema.d.ts` is regenerated from the merged `api/openapi.yaml`; if `arch-api` changed after the web commit, regenerate again before merging.
3. No `arch-deploy` change in this job.

## Out of scope
- Web forms, edit actions, the History tab and the delete confirmation (editing UI slice); any `arch-web` file other than `src/api/schema.d.ts`.
- Type (schema) management `POST|PATCH|DELETE /types/...`, `/admin/*` screens, the global audit query (`GET /history?actor=&source=...`), `entity` values other than `node` on `/history`.
- YAML import/export, `--prune`, the arch CLI; writing `source` other than `ui`.
- Any `arch-deploy` change (Helm values, RDS role, External Secrets for `MIGRATE_DATABASE_URL`).
- Editing hub files (`dev/env/arch-api.env`, `dev/postgres/init/*`), existing migrations, `.github/*`, or generated files by hand.
- `If-Match` on team/environment writes, a `version` column on teams/environments, merge-patch semantics for `attributes`, a GET for a single edge, secret checks on name/description/tags, cross-environment edges.
- Adding a JSON Schema library or changing role mapping, token validation or `accessMiddleware`.
- Writing `change_log` rows from `seed --sample` (dev-only sample data).

## Assumptions
- `entity_key` formats (`<environment>/<id>` for nodes, `uid` for edges, id for teams/environments) are not specified in the docs; chosen to be unique and readable.
- Edge history lookup uses partial jsonb expression indexes on `coalesce(after, before)` instead of a new column, to keep `change_log` exactly the columns of spec 003 Data; valid because an edge's environment/from/to are immutable.
- `actor_name` needs `preferred_username`, which `Principal` does not keep; a new `Principal.Username` field is added (identity package, not role mapping or token validation). Flagged because auth code is High risk.
- Attribute validation is hand-written for the documented subset (plus `minimum`/`maximum`, which the seeded `calls.port` uses) to avoid a new dependency; undeclared attributes are allowed (the seeded schemas don't set `additionalProperties`) but must be a supported value type, which is how "unknown attribute type" is read.
- Cross-environment edges cannot be expressed with the Contract's single `environment` field; they are rejected as a `to`/`from` not found in that environment (`422`).
- `If-Match: *`, weak or malformed values give `412`, so locking is never skipped (Decision 4).
- Permission is checked before reference validation, so an editor naming another team gets `403` even if other fields are wrong.
- The secret check covers attributes only, as [SPEC-model-10] says; extending it to name/description/tags would be a product decision.
- `/history` for an unknown or deleted node returns `200` with whatever rows exist (deleted nodes keep their history), not `404`; `limit` max 500 matches the other lists.
- `count` on `in-use` counts nodes (edges cannot exist without nodes).
- The migration grants `SELECT` on `goose_db_version` to `arch_app` so `/readyz` keeps working under the runtime role; this was not listed in the issue but is required by `VersionReader`.
- The role name `arch_app` is fixed in the migration, as [ADR-0014] names it; the deploy slice must create a role with that name on RDS.

## Docs impact
- [ADR-0014]: Status Proposed → Accepted (implemented here).
- [ADR-0005]: new ADR superseding it (ADRs are append-only, `docs/README.md`) with the spec 003 columns (`entity_key` instead of `entity_id`, `actor_name`, `environment` entity) and the trigger.
- `docs/specs/001_identity-access.md` Data: the `teams` claim matches `teams.id`, not `teams.name` (as [SPEC-admin-04] says).
- `docs/specs/003_editing-history.md` Data: add the `entity_key` formats and the edge-history expression indexes; Interfaces: add `428`, `409 /problems/in-use` and the `count` member.
- `docs/specs/008_admin.md` Interfaces: note the team and environment write endpoints shipped with this slice (types still pending).
- Hub follow-up (not a document): switch `DATABASE_URL` in `dev/env/arch-api.env` to `arch_app` after merge, as its comment and [ADR-0014] say.

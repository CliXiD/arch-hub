# Model tables, seeds and read API

> Issue #4: Model tables, seeds and read API

## Summary
- `arch-api` gets the typed graph of [002_model.md]: new goose migrations for `node_types`, `edge_types`, `teams`, `environments`, `nodes` and `edges`, plus a second migration that seeds the built-in vocabulary of [SPEC-model-02]..[SPEC-model-04] and the environments `dev`, `uat`, `prod`. This runs in every environment, prod included (Decision 1).
- sqlc is set up on the existing pgx pool, and seven viewer-only read endpoints go under `/api/v1`, with the shapes of the issue's Contract: one `{ items, next_cursor }` page shape, an opaque keyset cursor, `ETag` on single-node reads and a gzipped compact `GET /graph`.
- A new `arch-api seed --sample` subcommand loads a fixed 7-node, 7-edge example graph into `prod` for local development. It refuses, writing nothing, once any node exists (Decision 2).
- `arch-web` only regenerates `src/api/schema.d.ts` from the new `api/openapi.yaml`. Nothing changes in `arch-deploy`: no new env var, port or probe.
- The documents give only examples of allowed kind pairs, so this spec fixes the full default set, which intake proposed. The approver must confirm it, and `002_model.md` must record it afterwards.

## Context

**Documents.** [002_model.md] fixes the endpoints, page shape, ETag rule, graph compaction and tables ([SPEC-model-01]..[SPEC-model-08], Interfaces, Data). [ADR-0004] fixes PostgreSQL 16, pgx/v5 + sqlc and goose migrations in `arch-api/migrations/`. [SPEC-identity-access-04]: every viewer can read nodes, edges, types and teams. [NFR-001]: model attribute values are confidential and never go into logs or errors. [NFR-005]: `GET /graph` at 2,000 nodes and 10,000 edges answers in under 1 s server-side, gzip on. [ADR-0010]: integration tests use testcontainers behind `//go:build integration` and stay out of the gate. [ADR-0014] (Proposed): `migrate` uses `MIGRATE_DATABASE_URL` and `serve` uses `DATABASE_URL`. The `arch_app` grants come with the write slice, so this slice adds no grants.

**arch-api** (worktree at `origin/main`, the walking skeleton from job 001):
- `arch-api:cmd/arch-api/main.go`: `run(args, stdout, stderr) int` dispatches `serve` and `migrate up|status`. Anything else prints `usage` and returns `2`. Config errors return `1`. Tests are in `arch-api:cmd/arch-api/main_test.go`.
- `arch-api:internal/config/config.go`: `LoadServe` and `LoadMigrate` use the `reader` helper (`required`, `optional`, `invalid`, `result`). Errors name variables, never values. `isDatabaseURL` validates DSNs.
- `arch-api:internal/db/db.go`: `NewPool(databaseURL, tracing)` is a pgxpool that does not connect at start-up. The `otelpgx` tracer is used only when tracing is on. `arch-api:internal/db/migrate.go`: `Migrate` runs a goose v3 Provider over `migrations.FS`.
- `arch-api:migrations/00001_baseline.sql` is `SELECT 1` and is protected. `arch-api:migrations/embed.go` embeds `*.sql`. `health.Checker` compares the applied version with `db.LatestVersion(migrations.FS)`, so new migration files raise the expected version automatically.
- `arch-api:internal/httpapi/api.go`:
  - `NewAPI(r, Deps)` builds the Huma config.
  - `register[I, O](api, op, minRole, handler)` is the only way to add operations. It sets `Metadata["minRole"]`, bearer security and the 401/403 errors.
  - `accessMiddleware` puts the `auth.Principal` into the context.
  - `writeProblem` writes fixed-text RFC 9457 problems. `ProblemUnauthenticated` and `ProblemForbidden` are the existing problem types.
- `arch-api:internal/httpapi/routes.go` holds `registerRoutes(api, d)` with `/healthz`, `/readyz` and `/api/v1/me`. Response types are Go structs with Huma tags (`doc`, `enum`, `nullable:"false"`).
- `arch-api:internal/httpapi/engine.go`: `Deps{Auth, Ready, Logger, Metrics, CORSOrigins, Tracing}`. `NewEngine` sets the middleware order: recovery, otelgin, metrics, request log, CORS, then Huma. `cmd/openapi` calls `NewAPI(gin.New(), httpapi.Deps{})` with no dependencies, so new dependencies must be nil-safe at registration time.
- `arch-api:internal/httpapi/serve.go` wires the pool, the verifier and readiness into `NewEngine`.
- `arch-api:internal/httpapi/registry_test.go` holds the default-deny test. It walks every OpenAPI operation for a minimum role, bearer security and 401/403. `arch-api:internal/httpapi/httpapi_test.go` holds `newTestServer` with the `authtest` fake realm and token signer, the pattern for handler tests.
- `arch-api:internal/observability`: the request log records method, route template, status, duration, trace id and actor. It never records query strings, headers or bodies.
- `arch-api:Makefile` has `openapi` and `openapi-check`. `arch-api:go.mod` pins golangci-lint as a `tool` (`go tool golangci-lint`). There is no sqlc, no testcontainers and no model code yet. `arch-api:README.md` documents commands, config, endpoints and layout.
- The gate is `factory/checks/arch-api.sh`: vet, golangci-lint, `go test -count=1 ./...`, build and `make openapi-check`, with `-mod=readonly`.

**arch-web:**
- `arch-web:package.json` script `gen:api` runs `openapi-typescript ${ARCH_API_OPENAPI:-../arch-api/api/openapi.yaml} -o src/api/schema.d.ts`. In the job worktrees, `../arch-api` is this job's arch-api worktree.
- `arch-web:src/api/schema.d.ts` is generated and holds only `/healthz`, `/readyz` and `/api/v1/me` today. `arch-web:src/api/me.ts` and `client.ts` use it. No screen reads model data yet.

## Contract

The interface between `arch-api` (provider) and `arch-web` (consumer, types only in this slice) is `arch-api:api/openapi.yaml`, generated from the Huma types below.

**Common to every new operation.**
- Base path `/api/v1`, method `GET`, minimum role `viewer` through `register()`, bearer JWT. Responses are `application/json`; errors are RFC 9457 `application/problem+json` with `huma.ErrorModel`.
- Error types:
  - `401 /problems/unauthenticated` and `403 /problems/forbidden`: existing.
  - `404 /problems/not-found`: single-node read only.
  - `422 /problems/validation`: bad query or path parameter.
- A `422` problem lists each bad parameter in `errors[]` with `location` and `message` only. The `value` field is never filled: received values are never echoed, so `q` stays out of the body. `detail` is fixed text.

**Paging** (`GET /nodes`, `GET /edges`).
- `limit` is an integer, default `100`, minimum `1`, maximum `500`. `0`, `501` or a non-integer gives `422`.
- `cursor` is an optional opaque string. It is returned only as `next_cursor`; one that does not decode gives `422`.
- Response: `{ "items": [...], "next_cursor": string | null }`. `next_cursor` is always present and is `null` on the last page.
- Order is total and stable: nodes by `(environment, id)`, edges by `(environment, type, from_id, to_id)`. Keyset paging runs on that order.

**Types (JSON).**

```ts
type Kind = "application" | "infrastructure" | "network" | "external" | "team";
type Source = "ui" | "yaml" | "discovery" | "import";

type NodeType = { id: string; kind: Kind; name: string; attributes_schema: object; builtin: boolean };
type KindPair = { from: Kind; to: Kind };
type EdgeType = { id: string; name: string; attributes_schema: object; allowed: KindPair[]; builtin: boolean };
type Types = { node_types: NodeType[]; edge_types: EdgeType[] };            // each ordered by id

type Team = { id: string; name: string; created_at: string /* date-time */ };
type TeamList = { items: Team[] };                                         // ordered by id
type Environment = { id: string; name: string; sort: number /* integer */ };
type EnvironmentList = { items: Environment[] };                           // ordered by sort

type Node = {
  environment: string; id: string; kind: Kind; type: string; name: string; description: string;
  owner: string; attributes: object; tags: string[]; source: Source;
  created_at: string; updated_at: string; version: number /* integer */;
};
type Edge = {
  uid: string /* uuid */; environment: string; type: string; from: string; to: string;
  attributes: object; source: Source; created_at: string; updated_at: string; version: number;
};
type NodePage = { items: Node[]; next_cursor: string | null };
type EdgePage = { items: Edge[]; next_cursor: string | null };

type GraphNode = { id: string; kind: Kind; type: string; name: string; owner: string; tags: string[] };
type GraphEdge = { uid: string; type: string; from: string; to: string; attributes: object };
type Graph = { environment: string; nodes: GraphNode[]; edges: GraphEdge[] };  // nodes by id; edges by (type, from, to)
```

- All arrays (`items`, `tags`, `allowed`, `nodes`, `edges`) are never `null`. They are `[]` when empty, and marked `nullable:"false"` as `Me` already does. `attributes` and `attributes_schema` are always JSON objects. The Go schema names are the names above (`Node`, `Edge`, `NodePage`, ...).

**Endpoints.**

| operationId | path | query / path params | 200 body | other statuses |
|---|---|---|---|---|
| `list-types` | `/api/v1/types` | — | `Types` | 401, 403 |
| `list-teams` | `/api/v1/teams` | — | `TeamList` | 401, 403 |
| `list-environments` | `/api/v1/environments` | — | `EnvironmentList` | 401, 403 |
| `list-nodes` | `/api/v1/nodes` | `environment?`, `kind?` (enum `Kind`), `type?`, `owner?`, `q?` (max 200 chars, case-insensitive substring of `id` or `name`), `limit?`, `cursor?` | `NodePage` | 401, 403, 422 (bad `limit`/`cursor`/`kind`, unknown `environment`, `q` too long) |
| `get-node` | `/api/v1/nodes/{environment}/{id}` | path `environment`, `id` | `Node`, header `ETag: "<version>"` | 401, 403, 404 `/problems/not-found` (unknown environment or id) |
| `list-edges` | `/api/v1/edges` | `environment?`, `type?`, `from?`, `to?`, `limit?`, `cursor?` | `EdgePage` | 401, 403, 422 (bad `limit`/`cursor`, unknown `environment`) |
| `get-graph` | `/api/v1/graph` | `environment` (required) | `Graph` | 401, 403, 422 (missing or unknown `environment`) |

- Filters combine with AND. `type`, `owner`, `from` and `to` are exact matches. An unknown value for them returns an empty page, not `422`.
- `GET /api/v1/graph` answers with `Content-Encoding: gzip` and `Vary: Accept-Encoding` when the request's `Accept-Encoding` includes `gzip`, and plain JSON otherwise.
- Example: `GET /api/v1/nodes/prod/payments-api` gives `200`, `ETag: "1"`, and this body:
  ```json
  {"environment":"prod","id":"payments-api","kind":"application","type":"service","name":"Payments API",
   "description":"Sample: payments service","owner":"platform","attributes":{},"tags":[],"source":"import",
   "created_at":"2026-11-08T17:00:00Z","updated_at":"2026-11-08T17:00:00Z","version":1}
  ```

**Schema** (new migrations, owned by `arch-api` only [ADR-0004]; `repos.json` has no `rules`, and no other repo changes with it):

`arch-api:migrations/00002_model.sql` (Up creates the tables, Down drops them in reverse order):

| table | columns |
|---|---|
| `environments` | `id text PK CHECK (id ~ '^[a-z0-9][a-z0-9-]{1,62}$')`, `name text NOT NULL`, `sort integer NOT NULL UNIQUE` |
| `teams` | `id text PK` (same slug CHECK), `name text NOT NULL`, `created_at timestamptz NOT NULL DEFAULT now()` |
| `node_types` | `id text PK` (slug CHECK), `kind text NOT NULL CHECK (kind IN ('application','infrastructure','network','external','team'))`, `name text NOT NULL`, `attributes_schema jsonb NOT NULL DEFAULT '{"type":"object","properties":{}}'`, `builtin boolean NOT NULL DEFAULT false` |
| `edge_types` | `id text PK CHECK (id ~ '^[a-z][a-z0-9_]{1,62}$')`, `name text NOT NULL`, `attributes_schema jsonb NOT NULL DEFAULT '{"type":"object","properties":{}}'`, `allowed jsonb NOT NULL DEFAULT '[]'` (array of `{"from","to"}`), `builtin boolean NOT NULL DEFAULT false` |
| `nodes` | `environment text NOT NULL REFERENCES environments`, `id text NOT NULL CHECK (id ~ '^[a-z0-9][a-z0-9-]{1,62}$')`, `type text NOT NULL REFERENCES node_types`, `name text NOT NULL`, `description text NOT NULL DEFAULT ''`, `owner text NOT NULL REFERENCES teams`, `attributes jsonb NOT NULL DEFAULT '{}'`, `tags text[] NOT NULL DEFAULT '{}'`, `source text NOT NULL CHECK (source IN ('ui','yaml','discovery','import'))`, `created_at`/`updated_at timestamptz NOT NULL DEFAULT now()`, `version integer NOT NULL DEFAULT 1 CHECK (version >= 1)`; `PRIMARY KEY (environment, id)` |
| `edges` | `uid uuid PK DEFAULT gen_random_uuid()`, `environment text NOT NULL REFERENCES environments`, `type text NOT NULL REFERENCES edge_types`, `from_id text NOT NULL`, `to_id text NOT NULL`, `attributes jsonb NOT NULL DEFAULT '{}'`, `source` (same CHECK), `created_at`, `updated_at`, `version` (as nodes); `UNIQUE (environment, type, from_id, to_id)`; `FOREIGN KEY (environment, from_id) REFERENCES nodes (environment, id)` and the same for `to_id` |

- Every foreign key is the default `NO ACTION`: no cascade. Deletes are the write slice's job ([SPEC-model-09]).
- Indexes: `nodes (environment, type)`, `nodes (environment, owner)`, `edges (environment, from_id)` and `edges (environment, to_id)`. The primary key and the unique constraint already cover the paging orders.
- `kind` is not stored on `nodes`. Reads join `node_types` ([SPEC-model-01]: the type fixes the kind).
- No grants, no `change_log`.

`arch-api:migrations/00003_model_seed.sql` (Up inserts, Down deletes exactly these rows):
- Environments: `('dev','dev',1)`, `('uat','uat',2)`, `('prod','prod',3)`.
- Node types: all `builtin = true`, `attributes_schema = {"type":"object","properties":{}}`.

  | id | kind | name |
  |---|---|---|
  | `service` | application | Service |
  | `k8s-cluster` | infrastructure | Kubernetes cluster |
  | `database` | infrastructure | Database |
  | `queue` | infrastructure | Queue |
  | `bucket` | infrastructure | Bucket |
  | `vpc` | network | VPC |
  | `landing-zone` | network | Landing zone |
  | `transit-gateway` | network | Transit gateway |
  | `vpn` | network | VPN |
  | `direct-connect` | network | Direct Connect |
  | `firewall` | network | Firewall |
  | `on-prem-system` | external | On-prem system |
  | `saas` | external | SaaS |
  | `team` | team | Team |

- Edge types: all `builtin = true`, `attributes_schema = {"type":"object","properties":{}}` except `calls`.

  | id | name | allowed |
  |---|---|---|
  | `depends_on` | Depends on | application→application, application→infrastructure, application→external |
  | `calls` | Calls | application→application, application→external |
  | `runs_on` | Runs on | application→infrastructure |
  | `stores_data_in` | Stores data in | application→infrastructure |
  | `routes_via` | Routes via | application→network, network→network, network→application, network→external, infrastructure→network |
  | `owned_by` | Owned by | application→team, infrastructure→team, network→team, external→team |

- `calls.attributes_schema` [SPEC-model-03]:
  `{"type":"object","properties":{"protocol":{"type":"string","enum":["http","https","grpc","tcp","amqp","kafka","other"]},"port":{"type":"number","minimum":1,"maximum":65535}}}`
- No teams.

**Env vars / config.** None new. `seed --sample` reads the existing `DATABASE_URL`. `.env.example` and `arch-deploy` are unchanged.

**Compatibility.** Every operation is new; nothing existing is renamed or removed, and `/api/v1/me`, `/healthz` and `/readyz` are unchanged. The deployed `arch-web` ignores the new paths, and the regenerated `schema.d.ts` only adds types. During a rollout, `/readyz` on an old pod reports `migrations` once version 3 is applied, which is the existing behaviour for any new migration. The migrate job runs before the new pods.

## Requirements

### arch-api

**Migrations**
1. Add `migrations/00002_model.sql` and `migrations/00003_model_seed.sql` exactly as the Contract's Schema describes, each with goose `Up` and `Down` sections. Do not edit `migrations/00001_baseline.sql` or `migrations/embed.go` (protected).

**sqlc**

2. Set up sqlc:
   - Pin it as a `tool` in `go.mod`, as golangci-lint already is.
   - Add `sqlc.yaml` at the repo root: engine `postgresql`, schema `migrations/`, queries `internal/db/queries/`, output package `dbq` in `internal/db/dbq/`, `sql_package: pgx/v5`, JSON tags off.
   - Add `make sqlc` (`go tool sqlc generate`).
   - Commit the generated code and never hand-edit it.
   - Every query parameter (filters, `q`, cursor keys, limit) reaches SQL only as a sqlc parameter. `q` matches with `ILIKE`, with `%`, `_` and `\` escaped, against `id` and `name`.

**Read service**

3. Add a new package `internal/model`, a service over `dbq` and `*pgxpool.Pool`:
   - It returns types, teams, environments, node and edge pages, one node, and the graph.
   - It owns cursor encoding: base64url of the last row's sort key, decoded and validated on input. A bad cursor is a typed validation error.
   - It owns limit handling: it fetches `limit+1` rows to decide `next_cursor`.
   - It checks that the environment exists for the list and graph filters.
   - `Graph` reads nodes and edges in one `REPEATABLE READ READ ONLY` transaction, so they are a consistent snapshot.

**Handlers**

4. Add the handlers in `internal/httpapi`, kept thin, with a new `routes_model.go` or similar, and register them from `registerRoutes`:
   - Each operation goes through `register(..., Viewer, ...)` with the operationId, path, types and documented errors of the Contract: 404 on `get-node`, 422 on the list and graph operations.
   - Add a `Model` interface field to `Deps`, wired in `serve.go` with the `internal/model` service. It stays nil-safe for `cmd/openapi`.
   - Use Huma tags for `limit` (`default:"100" minimum:"1" maximum:"500"`), `kind` (enum) and `q` (`maxLength:"200"`).
   - The `ETag` is an output header field set to `"<version>"`, with the quotes.

**Problem mapping**

5. Map problems in one place in `internal/httpapi`, by setting `huma.NewError` from `NewAPI`:
   - `404` gets `type: /problems/not-found` and `422` gets `type: /problems/validation`.
   - Every `ErrorDetail.Value` is cleared, so no received value is echoed.
   - Other statuses keep Huma's default.
   - Database errors become `500` with fixed `detail` text. They are logged without query arguments or row data, and no attribute value appears in any problem `detail` or log line ([NFR-001]).

**Gzip**

6. Gzip `GET /api/v1/graph` when `Accept-Encoding` includes `gzip`, using `github.com/gin-contrib/gzip` in `NewEngine`. The repo already uses `gin-contrib/cors`. It may also cover other `/api/v1` JSON responses, but not `/metrics`, which is a separate server anyway.

**Seed command**

7. Add `arch-api seed --sample` to `cmd/arch-api/main.go` and to its `usage`:
   - Add a new `config.LoadSeed` that reads and validates `DATABASE_URL`, using the existing `reader` helper.
   - Add a new `internal/model` (or `internal/seed`) function that runs everything in one transaction:
     1. Refuse if `SELECT EXISTS (SELECT 1 FROM nodes)` is true: exit `1`, print `seed: the database already has nodes; nothing was written` on stderr, roll back.
     2. Otherwise insert teams `platform` ("Platform") and `core` ("Core"), with `ON CONFLICT (id) DO NOTHING`.
     3. Insert the sample graph and commit.
     4. Print `seeded sample graph: 7 nodes, 7 edges in prod` on stdout and exit `0`.
   - `seed` without `--sample`, or with any other argument, prints usage and exits `2`. A config error exits `1`.
   - Sample nodes: all environment `prod`, `source` `import`, `version` 1, `attributes` `{}`, `tags` `[]`, with a short description.

     | id | type | name | owner |
     |---|---|---|---|
     | `payments-api` | service | Payments API | platform |
     | `eks-prod` | k8s-cluster | EKS prod | platform |
     | `orders-db` | database | Orders DB | platform |
     | `core-banking` | on-prem-system | Core banking | core |
     | `vpc-prod` | vpc | VPC prod | platform |
     | `landing-zone` | landing-zone | Landing zone | platform |
     | `direct-connect` | direct-connect | Direct Connect | platform |

   - Sample edges: `source` `import`, `version` 1, attributes `{}` except `calls`.

     | type | from | to | attributes |
     |---|---|---|---|
     | `runs_on` | payments-api | eks-prod | `{}` |
     | `stores_data_in` | payments-api | orders-db | `{}` |
     | `calls` | payments-api | core-banking | `{"protocol":"https","port":443}` |
     | `routes_via` | payments-api | vpc-prod | `{}` |
     | `routes_via` | vpc-prod | landing-zone | `{}` |
     | `routes_via` | landing-zone | direct-connect | `{}` |
     | `routes_via` | direct-connect | core-banking | `{}` |

   - Every edge must satisfy its type's `allowed` pairs.

**Tests (unit, in the gate)**

8. Add table-driven unit tests with testify:
   - Each new handler, with a fake `Model` through `newTestServer`: shapes, `ETag`, 404, 422 for `limit=0`, `limit=501`, `limit=abc`, a bad cursor, an unknown `kind`, a missing graph `environment`, and no `value` in `errors[]`.
   - gzip on `/api/v1/graph` with and without `Accept-Encoding: gzip`.
   - Cursor encode/decode round trip and rejection.
   - The `seed` arguments and usage in `cmd/arch-api/main_test.go`.
   - `config.LoadSeed`.
   - The existing `TestEveryOperationDeclaresAMinimumRole` must cover the new operations unchanged.

**Integration test (out of the gate)**

9. Add an integration test behind `//go:build integration`, using `testcontainers-go` with a Postgres 16 module and image `postgres:16`. Add it to `go.mod`, so `-mod=readonly` still builds. It must:
   - Run `db.Migrate` up.
   - Assert the seeded types, `allowed` pairs, `calls` schema and environments.
   - Assert `GET /api/v1/teams` is empty.
   - Run `seed --sample`, assert the graph, then assert the second run refuses with the node count unchanged.
   - Page `GET /api/v1/nodes?environment=prod&limit=2` to the end.
   - Read `GET /api/v1/nodes/prod/payments-api` and its `ETag`.
   - Load 2,000 nodes and 10,000 edges into another environment, then assert `GET /api/v1/graph?environment=<env>` with `Accept-Encoding: gzip` takes under 1 s, measured around `engine.ServeHTTP` with an `authtest` token.

   Do not touch `.github/*` (protected). Wiring it into CI is left for a human.

**OpenAPI and docs**

10. Run `make openapi` and commit `api/openapi.yaml`.
11. Update `README.md`:
    - The opening paragraph: this slice adds the model.
    - Run it: `seed --sample`, and that it refuses on a non-empty database.
    - Endpoints: the seven new routes.
    - A short "Database code" section: `make sqlc`, never hand-edit `internal/db/dbq`.
    - Layout: `internal/model`, `internal/db/queries`, `internal/db/dbq`.
    - Documents: add `specs/002_model.md`.
    - How to run the integration tests: `go test -tags integration ./...`, which needs podman or docker.

### arch-web
1. Regenerate `src/api/schema.d.ts` with `pnpm gen:api` from this job's `../arch-api/api/openapi.yaml`, at the arch-api branch's final commit. Never hand-edit it. Make no other source change, and no screen changes.

## Acceptance criteria

The `curl` criteria assume the hub dev stack (`dev/bin/stack up` from the hub), the arch-api worktree's `.env` (`dev/bin/apply-env --to <arch-api worktree> arch-api`, then `set -a; . ./.env; set +a`), `go run ./cmd/arch-api migrate up` and `go run ./cmd/arch-api serve` from that worktree. They use a viewer-capable token:
`TOKEN=$(curl -s -d grant_type=client_credentials -d client_id=arch-ci-platform -d client_secret=dev-ci-secret http://localhost:8180/realms/arch/protocol/openid-connect/token | jq -r .access_token)`, then `H="Authorization: Bearer $TOKEN"`.

1. [arch-api] `ls migrations/` shows `00002_model.sql` and `00003_model_seed.sql`, and `git diff origin/main -- migrations/00001_baseline.sql migrations/embed.go .github` is empty.
2. [arch-api] After `migrate up` on an empty database, `curl -s -H "$H" localhost:8080/api/v1/types`:
   - lists the 14 node types and 6 edge types of [SPEC-model-02], all with `builtin: true`;
   - `calls.attributes_schema.properties` has `protocol` (with the 7-value enum) and `port` (`minimum` 1, `maximum` 65535);
   - `runs_on.allowed` is exactly `[{"from":"application","to":"infrastructure"}]`.
3. [arch-api] `curl -s -H "$H" localhost:8080/api/v1/environments` returns `items` with ids `dev`, `uat`, `prod` in that order. `curl -s -H "$H" localhost:8080/api/v1/teams` returns `{"items":[]}`.
4. [arch-api] `go run ./cmd/arch-api seed --sample` exits `0` and prints `seeded sample graph: 7 nodes, 7 edges in prod`. Then `curl -s -H "$H" 'localhost:8080/api/v1/graph?environment=prod'` returns:
   - 7 nodes, none of which has an `attributes` key;
   - 7 edges, the `calls` edge carrying `{"protocol":"https","port":443}`.
5. [arch-api] Running `go run ./cmd/arch-api seed --sample` a second time exits non-zero with the refusal message, and `psql "$DATABASE_URL" -tAc 'select count(*) from nodes'` still prints `7`.
6. [arch-api] `curl -s -H "$H" 'localhost:8080/api/v1/nodes?environment=prod&limit=2'` returns 2 items and a non-null `next_cursor`. Following `next_cursor` until it is `null` returns all 7 nodes exactly once, ordered by `id`.
7. [arch-api] `curl -s -o /dev/null -w '%{http_code}' -H "$H" 'localhost:8080/api/v1/nodes?limit=501'` prints `422`. The body has `"type":"/problems/validation"` and no `value` field. A bad cursor (`cursor=zzz`) and `environment=nope` also give `422`.
8. [arch-api] `curl -si -H "$H" localhost:8080/api/v1/nodes/prod/payments-api` shows `200`, `ETag: "1"`, and a body with `kind: "application"`, `owner: "platform"` and `attributes: {}`. `curl -si -H "$H" localhost:8080/api/v1/nodes/prod/nope` shows `404` with `"type":"/problems/not-found"`.
9. [arch-api] `curl -s -H "$H" 'localhost:8080/api/v1/edges?environment=prod&type=routes_via'` returns 4 edges and `next_cursor: null`. `curl -s -H "$H" 'localhost:8080/api/v1/nodes?environment=prod&q=PAY'` returns only `payments-api`.
10. [arch-api] `curl -si -H "$H" -H 'Accept-Encoding: gzip' 'localhost:8080/api/v1/graph?environment=prod' -o /dev/null -D -` shows `Content-Encoding: gzip`. Without `Accept-Encoding` there is no `Content-Encoding` header. `curl -s -o /dev/null -w '%{http_code}' -H "$H" localhost:8080/api/v1/graph` prints `422`.
11. [arch-api] Each of the seven new paths answers `401` with `/problems/unauthenticated` without a token, for example `curl -s -o /dev/null -w '%{http_code}' localhost:8080/api/v1/types` gives `401`. `go test ./internal/httpapi/ -run TestEveryOperationDeclaresAMinimumRole` passes.
12. [arch-api] `go test -tags integration -count=1 ./...` passes with podman or docker available, including the 2,000-node / 10,000-edge `GET /graph` under 1 s ([NFR-005]) and the second-seed refusal.
13. [arch-api] `go tool sqlc generate && git status --porcelain internal/db/dbq` prints nothing (the generated code is current). `api/openapi.yaml` contains the operationIds `list-types`, `list-teams`, `list-environments`, `list-nodes`, `get-node`, `list-edges` and `get-graph`.
14. [arch-api] `go run ./cmd/arch-api seed` and `go run ./cmd/arch-api seed --force` print the usage, which includes `seed --sample`, and exit `2`.
15. [arch-api] `README.md` documents `seed --sample`, the seven endpoints, `make sqlc` and the integration test command.
16. [arch-web] `pnpm gen:api && git diff --exit-code src/api/schema.d.ts` exits `0` with the arch-api worktree at its final commit. `grep -c '"/api/v1/graph"\|"/api/v1/nodes/{environment}/{id}"' src/api/schema.d.ts` is at least 2. `git diff origin/main --stat` lists only `src/api/schema.d.ts`.

## Merge and deploy order
1. **arch-api** first (`merge_order`). It carries the migrations, the endpoints and the `api/openapi.yaml` that `arch-web` generates from. On deploy, the migrate job applies `00002` and `00003` before the new pods serve.
2. **arch-web** second, after the arch-api PR merges. Its `schema.d.ts` must equal what `pnpm gen:api` produces from the merged `api/openapi.yaml`, so regenerate it if the arch-api PR changed after review. It only adds types, so it can deploy any time after arch-api.
3. **arch-deploy**: no change.

## Out of scope
- Write endpoints (create, update or delete of nodes, edges, types, teams or environments), `If-Match`, `412` and `428` handling, attribute-schema validation of writes, `409 /problems/in-use`.
- `change_log` table, history and triggers ([ADR-0005]), and secret detection ([SPEC-model-10]).
- `arch_app` grants and switching `DATABASE_URL` to `arch_app` ([ADR-0014]: write slice).
- Neighbourhood and impact queries (recursive CTEs), and extra traversal indexes beyond those listed.
- A single-edge read endpoint and an edge `ETag`. The Contract has no single-edge read.
- Cross-environment edges ([SPEC-model-07], Decision 6).
- Seeding any team by migration, or sample data in more than `prod`.
- Any web screen, hook or query in `arch-web`.
- Any change to `arch-deploy`, `.github/*`, the hub's `dev/` stack or the gate scripts.
- Full-text or trigram search for `q`, or new env vars.

## Assumptions
- Default `allowed` kind pairs are exactly the table above, intake's reading. [SPEC-model-04] gives only examples, and `routes_via` network→network is needed for the sample chain. Feedback 1 (accepted by the user) added `routes_via` network→application, network→external ([SPEC-app-focus-view-02]: a chain ends at the target node) and infrastructure→network.
- Display names: seeded environments use their id as `name`. Seeded types use the English names in the tables, sample teams are "Platform" and "Core", and the sample nodes use the names in the table. The documents give no names, and these are the plainest.
- `calls` `protocol` and `port` are optional (no `required`), and `port` is `"type":"number"` as [SPEC-model-03] words it. The spec states no required flags, and the write slice enforces schemas.
- Edge type ids use `snake_case` (`^[a-z][a-z0-9_]{1,62}$`), since the seeded ids `depends_on` and the others contain underscores. Node type, team and environment ids use the node slug pattern.
- Foreign keys do not cascade. [SPEC-model-09]'s delete with history belongs to the write slice, which can choose its own mechanism.
- `kind` is not a column on `nodes`. [SPEC-model-01] says the type fixes the kind, and [002_model.md] Data lists no `kind` on `nodes`.
- The unknown values that give `422` are only `environment` and `kind`, per intake. Unknown `type`, `owner`, `from` and `to` give empty pages, as plain filters do.
- `q` is capped at 200 characters. This bounds the `ILIKE` input; ids and names are short.
- `seed --sample` uses `DATABASE_URL`, not `MIGRATE_DATABASE_URL`, per intake. It writes data, not schema, and keeps working once `DATABASE_URL` becomes `arch_app` with DML grants. It upserts teams `platform` and `core` with `ON CONFLICT DO NOTHING`, because Decision 2 refuses only on existing nodes.
- Errors never echo received values. Huma's `ErrorDetail.value` is cleared, to keep `q` and other inputs out of responses ([NFR-001]).
- Gzip uses `gin-contrib/gzip` at the engine. This reuses the gin-contrib family already in `go.mod`, and Huma has no built-in compression.

## Docs impact
- `docs/specs/002_model.md`:
  - [SPEC-model-04]: record the full default `allowed` pairs of the six edge types.
  - [SPEC-model-03]: note that `calls` attributes are optional.
  - Data: note `edge_types.id` as snake_case, `kind` derived from `node_types` (not stored on `nodes`), and non-cascading foreign keys.
  - Interfaces: state that only `GET /nodes/{environment}/{id}` carries `ETag` until a single-edge read exists, and document the `422 /problems/validation` and `404 /problems/not-found` cases of the reads.
- `docs/specs/009_operations.md` Interfaces: add `arch-api seed --sample`, a local-development command that refuses when any node exists.
- `AGENTS.md` (hub) Local services, "Run an app natively": add the optional `go run ./cmd/arch-api seed --sample` step after `migrate up`.

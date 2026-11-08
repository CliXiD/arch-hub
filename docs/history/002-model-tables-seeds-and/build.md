STATUS: READY

# Build: Model tables, seeds and read API

## Summary
- arch-api now has the typed graph: migrations `00002_model.sql` (six tables, foreign keys that do not cascade, four indexes) and `00003_model_seed.sql` (14 node types, 6 edge types with their allowed pairs and the `calls` schema, environments dev/uat/prod).
- Round 2 (feedback 1): `routes_via` now also allows network→application, network→external and infrastructure→network, so a chain can end at the target node ([SPEC-app-focus-view-02]). The sample graph gains `direct-connect routes_via core-banking`, so it is now 7 nodes and 7 edges.
- sqlc runs on pgx/v5 and is pinned as a `go.mod` tool, with `make sqlc`. A new `internal/model` service handles keyset cursors, limit+1 paging, environment checks and a REPEATABLE READ READ ONLY graph snapshot.
- Seven viewer-only endpoints are registered through `register()`. Problems are mapped in one place (`huma.NewError`): 404 is `/problems/not-found`, 422 is `/problems/validation`, and `value` is always cleared. Only `GET /api/v1/graph` is gzipped (`gin-contrib/gzip`).
- `arch-api seed --sample` loads 7 nodes and 7 edges into prod in one transaction. It refuses, writing nothing, once any node exists.
- arch-web only regenerates `src/api/schema.d.ts`. PRs: CliXiD/arch-api#3, CliXiD/arch-web#3 (drafts, linked to each other).

## Changes
### arch-api
- `migrations/00002_model.sql`: `environments`, `teams`, `node_types`, `edge_types`, `nodes` and `edges` with the Contract's CHECKs, PKs, unique constraint and NO ACTION foreign keys. Indexes on `nodes (environment, type)`, `nodes (environment, owner)`, `edges (environment, from_id)` and `edges (environment, to_id)`. Down drops the tables in reverse order.
- `migrations/00003_model_seed.sql`: seeds the environments, node types and edge types as the Contract lists them, with `routes_via` allowing application→network, network→network, network→application, network→external and infrastructure→network (round 2). Down deletes exactly those rows. No teams.
- `internal/db/db_test.go`: the expected embedded migration version is now 3.
- `sqlc.yaml`: engine postgresql, schema `migrations/`, queries `internal/db/queries/`, package `dbq` in `internal/db/dbq`, pgx/v5, JSON tags off. Overrides map `timestamptz` to `time.Time` and `uuid` to `google/uuid`.
- `Makefile`: new `sqlc` target (`go tool sqlc generate`).
- `internal/db/queries/model.sql` and `seed.sql`: every filter, the ILIKE pattern, the cursor keys and the limit are sqlc parameters.
- `internal/db/dbq/*`: generated code, never hand-edited.
- `go.mod`/`go.sum`: sqlc v1.31.1 as a `tool`. New direct deps: `gin-contrib/gzip`, `google/uuid`, `testcontainers-go` and its postgres module (v0.45.0). No existing dependency was upgraded.
- `internal/model/types.go`: the JSON/Huma types (`Node`, `Edge`, `NodePage`, `Types`, `Graph`, ...). Arrays are `nullable:"false"` and `next_cursor` is `string|null` and required.
- `internal/model/errors.go`: `ErrNotFound`, `ErrNotEmpty`, and `ValidationError{Location, Message}`, which holds fixed text only.
- `internal/model/cursor.go`: the cursor is base64url (unpadded) of a JSON array holding the last row's sort key. Decoding checks the format and the number of key parts.
- `internal/model/service.go`: `Types`, `Teams`, `Environments`, `Nodes`, `Node`, `Edges` and `Graph`. Escapes `\ % _` for `q`, fetches limit+1 rows, rejects unknown environments with 422 and runs the graph in one RR/RO transaction. Timestamps are returned in UTC.
- `internal/model/seed.go`: `SeedSample`, one transaction that runs the EXISTS check and then the team upserts, nodes and edges. Round 2 adds the edge `direct-connect routes_via core-banking`.
- `internal/httpapi/api.go`: `ProblemNotFound` and `ProblemValidation`, and `newProblem` installed as `huma.NewError` in `NewAPI`.
- `internal/httpapi/engine.go`: new `Deps.Model` and gzip middleware for `/api/v1/graph`.
- `internal/httpapi/serve.go`: wires `model.NewService(pool)`.
- `internal/httpapi/routes.go`: calls `registerModelRoutes`.
- `internal/httpapi/routes_model.go`: the `Model` interface and seven thin handlers. A failure maps to 404, 422, or a 500 with fixed text, logged as `operation` plus `error_class` (SQLSTATE or Go type, never the message).
- `cmd/arch-api/main.go`: `seed --sample` and its usage line.
- `internal/config/config.go`: `LoadSeed` (DATABASE_URL).
- `api/openapi.yaml`: regenerated (`make openapi`).
- `README.md`: intro, Run it (seed), the endpoints and paging/problem rules, a Database code section, the integration test command, Layout and Documents.
- Tests:
  - `internal/httpapi/routes_model_test.go`: shapes, ETag, 404, 422 cases with no `value`, the 500 path that leaks nothing, 401 on all seven routes, gzip on and off.
  - `internal/model/cursor_test.go`: cursor round trip, rejected cursors, LIKE escaping.
  - `internal/config/config_test.go`: `TestLoadSeed`.
  - `cmd/arch-api/main_test.go`: seed arguments.
  - `cmd/arch-api/integration_test.go` (`//go:build integration`).

### arch-web
- `src/api/schema.d.ts`: regenerated with `pnpm gen:api` from the arch-api branch's final `api/openapi.yaml`. No other change.

### arch-deploy
- Not in the job and needs no change: no new env var, port or probe.

## Acceptance criteria
Round 2 re-ran the affected live checks (2, 4, 5, 9) after the stack reset, on a fresh scratch database `arch_job002` that was dropped afterwards. For the live checks, the job's arch-api ran against the hub dev stack on a throwaway database `arch_job002`, so the shared `arch` database was untouched. `migrate up` ran on an empty database, then `serve` on :5160 and `seed --sample`. The token came from `arch-ci-platform`. The database was dropped afterwards.

1. [x] [arch-api] `ls migrations/` shows `00001_baseline.sql 00002_model.sql 00003_model_seed.sql embed.go`. `git diff origin/main --stat -- migrations/00001_baseline.sql migrations/embed.go .github` is empty.
2. [x] [arch-api] `/api/v1/types` returns 14 node types and 6 edge types, all `builtin: true`. `calls.attributes_schema.properties` has `protocol` (7-value enum) and `port` (min 1, max 65535). `runs_on.allowed` is `[{"from":"application","to":"infrastructure"}]`. Round 2: `routes_via.allowed` is `[application→network, network→network, network→application, network→external, infrastructure→network]`.
3. [x] [arch-api] `/api/v1/environments` returns ids `["dev","uat","prod"]` in that order. `/api/v1/teams` returns `{"items":[]}`.
4. [x] [arch-api] `seed --sample` exits 0 and prints `seeded sample graph: 7 nodes, 7 edges in prod` (round 2; spec updated per feedback 1). The graph has 7 nodes, none with an `attributes` key, and 7 edges, with the `routes_via` chain `payments-api > vpc-prod > landing-zone > direct-connect > core-banking`. Every sample edge satisfies its type's allowed pairs (integration test); the `calls` edge has `{"port":443,"protocol":"https"}`.
5. [x] [arch-api] The second `seed --sample` exits 1 with `seed: the database already has nodes; nothing was written`, and `select count(*) from nodes` still prints `7`.
6. [x] [arch-api] `nodes?environment=prod&limit=2` returns 2 items and a cursor. Following the cursors gives `core-banking direct-connect eks-prod landing-zone orders-db payments-api vpc-prod` over 4 pages.
7. [x] [arch-api] `limit=501` gives 422 with `{"type":"/problems/validation",...,"errors":[{"message":"expected number <= 500","location":"query.limit"}]}`, which has no `value`. `cursor=zzz` and `environment=nope` also give 422.
8. [x] [arch-api] `nodes/prod/payments-api` gives `200`, `Etag: "1"`, and a body with `kind: "application"`, `owner: "platform"`, `attributes: {}` and UTC timestamps. `nodes/prod/nope` gives `404` with `"type":"/problems/not-found"`.
9. [x] [arch-api] `edges?environment=prod&type=routes_via` returns 4 items (round 2; was 3) and `next_cursor: null`. `nodes?environment=prod&q=PAY` returns `["payments-api"]`.
10. [x] [arch-api] With `Accept-Encoding: gzip`, the graph response has `Content-Encoding: gzip` and `Vary: Accept-Encoding`. Without it there is no `Content-Encoding`. `/api/v1/graph` with no environment gives `422`.
11. [x] [arch-api] All seven paths give `401` with `/problems/unauthenticated` without a token, both live and in `TestModelRoutesNeedAToken`. `TestEveryOperationDeclaresAMinimumRole` passes unchanged.
12. [x] [arch-api] `go test -tags integration -count=1 -run TestModelIntegration ./cmd/arch-api/` passes on podman (`DOCKER_HOST=<podman machine socket>`, `TESTCONTAINERS_RYUK_DISABLED=true`). This is the package that holds the integration test; the other packages were checked by the gate. `GET /graph` over 2,000 nodes and 10,000 edges with gzip took 41 ms (265 KB). The second seed is refused and the node count stays 7.
13. [x] [arch-api] `go tool sqlc generate && git status --porcelain internal/db/dbq` prints nothing. `api/openapi.yaml` has all 7 operationIds (`grep -c` gives 7).
14. [x] [arch-api] The built binary prints usage (with `seed --sample`) and exits 2 for both `seed` and `seed --force`. `go run` itself reports `exit status 2`. This is also unit-tested in `TestRun`.
15. [x] [arch-api] `README.md` documents `seed --sample`, the seven endpoints, `make sqlc` and `go test -tags integration ./...`.
16. [x] [arch-web] `pnpm gen:api` against the final arch-api commit leaves `src/api/schema.d.ts` unchanged. `grep -c` for the graph and node paths gives 2. `git diff origin/main --stat` lists only `src/api/schema.d.ts`.

Extra checks:
- `GET /api/v1/graph` in round 2's integration run took 41 ms.
- The Down sections of 00003 and then 00002, run by hand after clearing the sample rows, leave 0 seeded rows and then 0 model tables.
- `q=%25` matches nothing, so `%` is matched literally.
- `q` over 200 characters gives 422 `expected length <= 200` with no value echoed.

## Validation
- arch-api:
  - `FACTORY_HUB=... FACTORY_REPO_KEY=arch-api FACTORY_BASE=origin/main bash factory/checks/arch-api.sh` exits 0 (vet, golangci-lint 0 issues, unit tests, build, openapi-check).
  - `go vet -tags integration ./...` and `go tool golangci-lint run --build-tags integration ./...` pass (0 issues).
  - `go test -tags integration -count=1 -run TestModelIntegration ./cmd/arch-api/` passes (13 s).
- arch-web: `FACTORY_HUB=... FACTORY_REPO_KEY=arch-web FACTORY_BASE=origin/main bash factory/checks/arch-web.sh` exits 0 (lint, typecheck, 24 tests, build).

## Notes for reviewers
- Huma adds a `422` response to `get-node` in `openapi.yaml` by itself, because the operation has path parameters. It cannot happen at runtime, since both path params are plain strings. The documented `404` is there as the Contract requires.
- `allowed` kind pairs follow the spec's table. Per feedback 1, the user accepted the recommendation to extend `routes_via`, and the job's `spec.md` table, sample edges and counts were updated to match. The Docs impact updates (`002_model.md`, `009_operations.md`, hub `AGENTS.md`) are hub documents and are not part of this build.
- The integration test is in `cmd/arch-api` so that it runs the real `seed --sample` through `run()`. It is not wired into CI, because `.github` is protected.

## Log
### Round 1
- Implemented spec.md in arch-api in merge order: migrations, sqlc and queries, the model service and handlers, problem mapping, gzip, the seed command, tests, the integration test, OpenAPI and README. Then regenerated the arch-web types.
- The model types are defined once in `internal/model`, with Huma tags, so the OpenAPI schema names match the Contract (`Node`, `Edge`, `NodePage`, ...).
- Normalised timestamps to UTC after a live check showed pgx returning local-zone times (`+07:00`). The Contract's example uses `Z`.
- Pushed `factory/002-model-tables-seeds-and` in both repos. Opened draft PRs CliXiD/arch-api#3 and CliXiD/arch-web#3 and linked them to each other.

### Round 2
Feedback 1: the user accepted the recommendation to extend the `routes_via` pairs.
- `migrations/00003_model_seed.sql` (new on this branch and not merged, so editing it is allowed): `routes_via.allowed` adds network→application, network→external and infrastructure→network.
- `internal/model/seed.go`: adds the sample edge `direct-connect routes_via core-banking` (network→external), which completes the [SPEC-app-focus-view-02] example chain. Sample counts are now 7 nodes and 7 edges.
- `cmd/arch-api/integration_test.go`: the expected `routes_via` pairs, edge counts (7), the `routes_via` filter (4) and the seed message are updated. `README.md` now says 7 edges.
- The job's `spec.md` is updated as the feedback asked: the allowed-pairs table, the sample edges table, the counts in Summary and acceptance criteria 4 and 9, and the Assumption. `docs/specs/002_model.md` stays in Docs impact for after approval.
- One new commit, `7dd2588` "feat: let routes_via reach the target and start from infrastructure", pushed. The CliXiD/arch-api#3 body is updated.
- `api/openapi.yaml` is unchanged (`make openapi-check` passes), so arch-web needs no change this round.
- Validation: the arch-api gate exits 0, integration lint reports 0 issues, sqlc output is current, and the integration test passes on podman. Live checks on a scratch database on the reset stack: `migrate up`, `seed --sample` (7/7), refusal on the second run, `/types` `routes_via.allowed`, the graph's 7 edges with the full chain, and the `routes_via` filter returning 4.


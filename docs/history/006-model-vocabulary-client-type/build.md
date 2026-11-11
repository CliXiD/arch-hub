STATUS: READY

# Build: Widen the built-in model vocabulary (client, load balancer, registry, job; external callers; edge attributes)

## Summary
- New goose migration `migrations/00006_model_vocabulary.sql` in arch-api seeds four built-in node types, adds `external → application` (last) to `calls` and `depends_on`, and widens the `calls` and `stores_data_in` attribute schemas. Down restores the 00003 literals and then deletes the four types.
- No Go behaviour change: `internal/model`, `internal/httpapi`, `internal/db/dbq` and `api/openapi.yaml` are untouched (`make openapi-check` is clean).
- Tests: version pins 5 → 6, the "seeded vocabulary" assertions now match the new state, a new "wider vocabulary" write subtest, and a new rollback test `TestMigrationVocabularyRollback`.
- Draft PR: https://github.com/CliXiD/arch-api/pull/7

## Changes
### arch-api
- `migrations/00006_model_vocabulary.sql` (new): Up inserts `client`/external, `load-balancer`/network, `container-registry`/infrastructure, `job`/application (builtin, default schema). It appends `{"from":"external","to":"application"}` to `allowed` of `calls` and `depends_on` and sets the new `calls` and `stores_data_in` schemas exactly as the spec gives them. Down first restores `allowed` and `attributes_schema` of `stores_data_in`, `calls` and `depends_on` to their 00003 literals, then deletes the four node types by id. It deletes no nodes or edges.
- `internal/db/db_test.go`: `TestEmbeddedMigrations` expects 6.
- `cmd/arch-api/integration_test.go`: moved the container start and the `arch_app` role creation into `startEmptyPostgres` (no migrations). `startPostgres` calls it and returns the same values as before. "seeded vocabulary" now expects 18 node types, the new last pair on `calls` and `depends_on`, the new `calls` schema, and (new) the `stores_data_in` schema.
- `cmd/arch-api/write_integration_test.go`: "readiness as arch_app" expects 6. A new subtest "wider vocabulary" runs after "create edges". It creates `browser` (client), `nightly-reconcile` (job) and `ghcr` (container-registry), all owned by `platform`, and then checks:
  - `calls` and `depends_on` from browser to payments-api → 201;
  - `calls` from nightly-reconcile to payments-api with `otlp` and `/api/v1` → 201;
  - `stores_data_in` from payments-api to ghcr with `{port:5432, role:arch_app}` → 201;
  - `smtp` → 422 at `body.attributes.protocol`;
  - `port 70000` on `stores_data_in` → 422 at `body.attributes.port`;
  - `/graph?environment=prod` lists the browser → payments-api `calls` edge.

  Later subtests were updated for the extra rows: "history" has 4 more `edge create editor` entries, "in use" expects 7 platform nodes and 8 prod nodes, and "deleting a node deletes its edges" also expects the 4 new edges to be cascade-deleted (3+4 rows). gofmt realigned two existing comment lines in the history list.
- `cmd/arch-api/migrate_integration_test.go` (new, `//go:build integration`): `TestMigrationVocabularyRollback` runs on its own container. It builds a goose provider over `migrations.FS` (database/sql + pgx stdlib), runs `UpTo(5)` and snapshots `to_jsonb` of every `node_types` and `edge_types` row ordered by id. It then runs `UpTo(6)` and asserts the snapshot changed, runs `Down` and asserts version 5 and that every row JSON-equals the version-5 snapshot.

## Acceptance criteria
1. [x] [arch-api] 00006 exists with Up/Down sections; `git diff --name-only origin/main -- migrations/` prints only `migrations/00006_model_vocabulary.sql`.
2. [x] [arch-api] `/api/v1/types` lists the four new types, each builtin: "seeded vocabulary" PASS in `go test -tags integration -count=1 -run TestModelIntegration ./cmd/arch-api/`.
3. [x] [arch-api] client → application `calls` gives 201, `depends_on` gives 201, and the `calls` edge is in `/graph?environment=prod`: `TestWriteIntegration/wider_vocabulary` PASS.
4. [x] [arch-api] `otlp` + `path` gives 201; `smtp` gives 422 at `body.attributes.protocol`: same subtest (`protocol_not_in_the_enum` PASS).
5. [x] [arch-api] `stores_data_in` `{5432, arch_app}` gives 201; `70000` gives 422 at `body.attributes.port`: same subtest (`stores_data_in_port_out_of_range` PASS).
6. [x] [arch-api] Up to 6 then Down gives version 5 and the vocabulary equal to version 5: `go test -tags integration -count=1 -run TestMigrationVocabularyRollback ./cmd/arch-api/` PASS.
7. [x] [arch-api] The existing write subtests pass, including `rejected_writes_leave_no_row/unsupported_attribute_type`, `kind_pair_not_allowed` (runs_on) and `port_out_of_range`. `go test -tags integration -count=1 ./...` passes for every package (podman with `DOCKER_HOST` set to the podman socket and `TESTCONTAINERS_RYUK_DISABLED=true`, as the README describes).
8. [x] [arch-api] `go test -count=1 ./internal/db/` passes with `TestEmbeddedMigrations` expecting 6. `make openapi-check` exits 0 with no diff, and `git diff origin/main -- api internal/model internal/httpapi internal/db/dbq` is empty.

## Validation
### arch-api
- `FACTORY_HUB=... FACTORY_REPO_KEY=arch-api FACTORY_BASE=main bash factory/checks/arch-api.sh`: PASS (go vet, golangci-lint 0 issues, unit tests, build, openapi-check).
- `go vet -tags integration ./...`: PASS.
- `go tool golangci-lint run --build-tags integration ./cmd/...`: 0 issues.
- `go test -tags integration -count=1 ./...`: PASS.
- `go test -tags integration -count=1 -v -run 'TestMigrationVocabularyRollback|TestWriteIntegration|TestModelIntegration' ./cmd/arch-api/`: all subtests PASS.

## Log
### Round 1
- Implemented the spec in arch-api in two commits: the migration with the version pin, then the integration tests. Pushed `factory/006-model-vocabulary-client-type` and opened draft PR CliXiD/arch-api#7 against `main`.
- First integration run failed in my own new subtest: I reused one `model.Edge` across the decodes, so `json.Unmarshal` merged attribute maps. I now reset it for each request.
- Chose to adjust the later subtests ("history", "in use", "deleting a node deletes its edges") to the extra rows, because the spec requires the new edges to touch `payments-api`.

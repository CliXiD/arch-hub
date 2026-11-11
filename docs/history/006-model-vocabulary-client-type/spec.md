# Widen the built-in model vocabulary (client, load balancer, registry, job; external callers; edge attributes)

> Issue #17: Model vocabulary: client type, more built-in types, external callers, richer edge attributes

## Summary
- One new goose migration in `arch-api` (`migrations/00006_model_vocabulary.sql`) adds four built-in node types, the `external → application` pair on `calls` and `depends_on`, and new attributes on `calls` and `stores_data_in`. Its Down reverses exactly those changes.
- No Go behaviour change is needed: edge writes read `allowed` and `attributes_schema` from the `edge_types` row on every write, and the validator already handles `enum`, `minimum` and `maximum`.
- The tests that pin the current vocabulary and migration version get the new values, and new integration tests cover the acceptance criteria and the Up/Down round trip.
- The hub documents already describe the result ([SPEC-model-02], [SPEC-model-03], [SPEC-model-04] cite issue #17). This job only implements them.
- `api/openapi.yaml`, `arch-web` and `arch-deploy` stay unchanged.

## Context
**Vocabulary today.** `arch-api:migrations/00003_model_seed.sql` (protected, never edited) seeds 14 built-in `node_types` and 6 built-in `edge_types`. The table definitions are in `arch-api:migrations/00002_model.sql`:
- `node_types(id, kind, name, attributes_schema jsonb DEFAULT '{"type":"object","properties":{}}', builtin)`
- `edge_types(id, name, attributes_schema jsonb, allowed jsonb DEFAULT '[]', builtin)`

`nodes.type` references `node_types` with no `ON DELETE`, so a node type that nodes use can't be deleted. The current values that matter here, as in 00003:
- `calls.allowed` = `[{"from":"application","to":"application"},{"from":"application","to":"external"}]`
- `depends_on.allowed` = `[{"from":"application","to":"application"},{"from":"application","to":"infrastructure"},{"from":"application","to":"external"}]`
- `calls.attributes_schema` = `{"type":"object","properties":{"protocol":{"type":"string","enum":["http","https","grpc","tcp","amqp","kafka","other"]},"port":{"type":"number","minimum":1,"maximum":65535}}}`
- `stores_data_in.attributes_schema` = `{"type":"object","properties":{}}`

**Write path.** `arch-api:internal/model/write.go` `CreateEdge` (and the edge update path) loads the edge type with `q.GetEdgeType`, unmarshals `Allowed` into `[]KindPair` and calls `checkKindPair`. It then runs `validateAttributes` (`arch-api:internal/model/validate.go`: `type`, `enum`, `minimum`, `maximum`, `required`, `additionalProperties`; undeclared attributes are allowed) and `CheckSecrets`. `GET /api/v1/types` and `GET /api/v1/graph` read the tables directly. There is no impact-query code yet, so `/graph` is the only traversal read in scope.

**Migrations and readiness.**
- `arch-api:internal/db/migrate.go` runs goose through `goose.NewProvider(goose.DialectPostgres, sqlDB, migrations.FS)` and supports only `up` and `status`. `arch-api:cmd/arch-api/main_test.go` asserts that `migrate down` is rejected.
- `arch-api:internal/httpapi/serve.go` sets readiness to expect `db.LatestVersion(migrations.FS)`.
- `arch-api:internal/db/db_test.go` `TestEmbeddedMigrations` asserts that the latest embedded version is `5`.
- `arch-api:cmd/arch-api/write_integration_test.go` ("readiness as arch_app") asserts that the applied version is `5`.
- Every migration file starts with a one-line comment, then `-- +goose Up` and `-- +goose Down` (see `00003`, `00005`).

**Tests.**
- Integration tests (`//go:build integration`, testcontainers Postgres 16) live in `arch-api:cmd/arch-api/`.
- `integration_test.go` provides `startPostgres` (creates `arch_app`, migrates fully as the owner), `newPool`, `newEngine` and `client`. Its `TestModelIntegration` "seeded vocabulary" subtest asserts the exact node type → kind map, every edge type's `allowed`, the `calls` schema, and that every node type has the empty schema.
- `write_integration_test.go` provides the `writer.expect` helper, `problemBody`, the `editor` token (team `platform`) and the `admin` token. Its `TestWriteIntegration` subtests build on each other: teams `platform`/`core` are created first, then nodes `payments-api` (service), `ledger`, `core-banking` (on-prem-system), `eks-prod`, `vpc-prod`.

**Documents.** [BR-001]; [SPEC-model-01] (kinds are fixed); [SPEC-model-02] (default types incl. `job`, `container-registry`, `load-balancer`, `client`); [SPEC-model-03] (`calls` protocol enum incl. `postgres`/`otlp`, `path`; `stores_data_in` `port`/`role`); [SPEC-model-04] (`calls` and `depends_on` allow external → application); [SPEC-admin-03] (built-ins can't be deleted or renamed); [ADR-0004] (goose migrations, never edit an existing one).

## Contract
Single repo; no contract. (No endpoint, request or response shape changes, and `api/openapi.yaml` stays unchanged. The data the migration writes is listed under Requirements.)

## Requirements

### arch-api

1. Add a new file `migrations/00006_model_vocabulary.sql`. Start it with a one-line comment that names hub issue #17, then `-- +goose Up` and `-- +goose Down`, like the existing migrations. Don't edit or delete any existing migration.
2. **Up: node types.** Insert four rows into `node_types` with `builtin = true` and the default `attributes_schema`:
   | id | kind | name |
   |---|---|---|
   | `client` | `external` | `Client or actor` |
   | `load-balancer` | `network` | `Load balancer / ingress` |
   | `container-registry` | `infrastructure` | `Container registry` |
   | `job` | `application` | `Job` |
3. **Up: kind pairs.** Append `{"from":"external","to":"application"}` as the last element of `allowed` for `calls` and for `depends_on`. Existing pairs keep their order. For example, use `allowed || '[{"from":"external","to":"application"}]'::jsonb`.
4. **Up: attribute schemas.**
   - Set `calls.attributes_schema` to:
     `{"type":"object","properties":{"protocol":{"type":"string","enum":["http","https","grpc","tcp","amqp","kafka","postgres","otlp","other"]},"port":{"type":"number","minimum":1,"maximum":65535},"path":{"type":"string"}}}`
   - Set `stores_data_in.attributes_schema` to:
     `{"type":"object","properties":{"port":{"type":"number","minimum":1,"maximum":65535},"role":{"type":"string"}}}`
   - Don't mark any property `required` and don't set `additionalProperties`, so undeclared attributes stay accepted (Decision 6).
5. **Down: exact reversal.**
   - Restore `allowed` and `attributes_schema` of `calls`, `depends_on` and `stores_data_in` to their 00003 literals (quoted in Context).
   - Delete the four node types by id.
   - Order the statements so the edge-type updates run first. Down must not delete nodes or edges. If nodes still use a new type, the foreign key makes Down fail, and that is intended.
6. **No Go behaviour change.**
   - Leave `internal/model`, `internal/httpapi`, sqlc output (`internal/db/dbq`) and `api/openapi.yaml` untouched. `make openapi-check` must still pass with no diff.
   - Don't add a `migrate down` subcommand. `main_test.go` keeps rejecting it.
7. **Version-pinned tests.** Update the expected version from `5` to `6` in `internal/db/db_test.go` `TestEmbeddedMigrations` and in `cmd/arch-api/write_integration_test.go` "readiness as arch_app".
8. **Seeded vocabulary test.** Update `cmd/arch-api/integration_test.go` "seeded vocabulary" to the new state:
   - the node type map has 18 entries, including the four new ones with their kinds, all `builtin` and with the empty schema;
   - the new `external → application` pair is last in `calls` and `depends_on`;
   - the `calls` schema equals the new literal;
   - a new assertion checks that the `stores_data_in` schema equals its new literal.
9. **Write cases.** Add a subtest to `TestWriteIntegration` in `cmd/arch-api/write_integration_test.go`, after "create edges" and reusing `writer.expect`, `problemBody` and the existing nodes. It must:
   - create a `client` node (for example `prod/browser`, owner `platform`);
   - `POST /api/v1/edges` `calls` from it to `payments-api` → `201`, and `depends_on` from it to `payments-api` → `201`;
   - `calls` from an application to another with `{"protocol":"otlp","path":"/api/v1"}` → `201`, using a pair not taken yet so the unique key doesn't give `409`. For example, create a `job` node and send `job → payments-api`; this also exercises the `job` type;
   - `calls` with `{"protocol":"smtp"}` → `422`, `/problems/validation`, location `body.attributes.protocol`;
   - `stores_data_in` from `payments-api` to a new `container-registry` or `database` node with `{"port":5432,"role":"arch_app"}` → `201`;
   - `stores_data_in` with `{"port":70000}` → `422` at `body.attributes.port`;
   - `GET /api/v1/graph?environment=prod` lists the `client → payments-api` `calls` edge.

   Later subtests that count nodes, edges or `change_log` rows must still pass. Either adjust their expectations or pick ids that don't collide.
10. **Rollback test.** Add `cmd/arch-api/migrate_integration_test.go` (`//go:build integration`) with a test on its own container:
    1. Migrate to version 5 only: a goose provider over `migrations.FS` and `UpTo(ctx, 5)`, using the same `database/sql` + `pgx` stdlib setup as `internal/db/migrate.go`.
    2. Snapshot every row of `node_types` and `edge_types`, ordered by id, with jsonb columns compared as JSON (for example `SELECT to_jsonb(t) FROM node_types t ORDER BY id`).
    3. Run Up to version 6 and assert that the snapshot changed.
    4. Run `Down` one step and assert that the goose version is `5` and the snapshot equals the one from step 2.

    Factor shared container setup out of `startPostgres` where needed, without changing what `startPostgres` returns to its current callers.

## Acceptance criteria
1. [arch-api] `migrations/00006_model_vocabulary.sql` exists with `-- +goose Up` and `-- +goose Down` sections, and `git diff --name-only origin/main -- migrations/` lists only that file. Check with `cd <worktree> && git diff --name-only origin/main -- migrations/`.
2. [arch-api] `GET /api/v1/types` lists `client`/`external`, `load-balancer`/`network`, `container-registry`/`infrastructure` and `job`/`application`, each with `builtin: true`. Check with the "seeded vocabulary" subtest of `go test -tags integration -count=1 -run TestModelIntegration ./cmd/arch-api/`.
3. [arch-api] `POST /api/v1/edges` with `calls` from a `client` node to an application gives `201`, and the same with `depends_on` gives `201`. The `calls` edge appears in `GET /api/v1/graph?environment=prod`. Check with the new subtest in `go test -tags integration -count=1 -run TestWriteIntegration ./cmd/arch-api/`.
4. [arch-api] `calls` with `protocol: otlp, path: "/api/v1"` gives `201`; `protocol: smtp` gives `422` at `body.attributes.protocol`. Same command as 3.
5. [arch-api] `stores_data_in` with `port: 5432, role: "arch_app"` gives `201`; `port: 70000` gives `422` at `body.attributes.port`. Same command as 3.
6. [arch-api] After `migrate up` to 6 and goose `Down` one step, `node_types` and `edge_types` equal their state at version 5 and the applied version is 5. Check with `go test -tags integration -count=1 -run <rollback test name> ./cmd/arch-api/`.
7. [arch-api] Existing writes still behave as before: the existing `TestWriteIntegration` subtests pass, including the undeclared-attribute and `runs_on` kind-pair cases, and so does the whole `go test -tags integration -count=1 ./...`.
8. [arch-api] `go test -count=1 ./internal/db/` passes with `TestEmbeddedMigrations` expecting `6`, and `make openapi-check` reports no diff (`api/openapi.yaml` is unchanged).

## Merge and deploy order
1. Merge `arch-api` alone. `arch-web` and `arch-deploy` have no change.
2. On deploy, the migrate job applies version 6 before the new API pods start. This follows the existing Helm order in [ADR-0009]: the migrate job, then the rollout.
3. Readiness compares the applied version with the image's latest embedded one, so pods still on the old image report `/readyz` 503 (`migrations`) until the rollout replaces them. This is the existing behaviour for every migration, not something this job introduces.
4. Old pods still write correctly against the new data, because they read `allowed` and schemas from the database.

## Out of scope
- Admin endpoints or UI for adding or editing types (separate issue, [SPEC-admin-03]).
- Any change to the hub's dogfood model or infographic (`docs/architecture/`).
- A `migrate down` CLI subcommand. The rollback is tested with goose directly.
- A new node kind (Decision 1), a Helm-release type (Decision 2), an `oidc` protocol value (Decision 3).
- The `body.from` vs `body.to` location rule for disallowed pairs from [SPEC-model-04] (hub issue #18).
- Impact-query code: none exists yet, so this job doesn't add or change any.
- Editing `00003_model_seed.sql` or any other existing migration, `internal/db/dbq`, `api/openapi.yaml`, the YAML JSON Schema, `arch-web` or `arch-deploy`.
- Making any new attribute required, or setting `additionalProperties: false`.

## Assumptions
- **Migration file name.** The file is `00006_model_vocabulary.sql`. It follows the existing `<version>_<topic>.sql` naming, and 5 is the latest version.
- **Down restores literals.** Down restores the 00003 literals instead of removing just the added keys or pair. jsonb has no "remove object from array" operator, and no admin endpoint can have changed built-in types since, so the literals are the exact prior state.
- **Down doesn't delete data.** Down fails, rather than deleting data, when nodes use a new type or edges rely on the new pair. Rolling back must not destroy model data. The existing FK already gives this, and edges using the new pair simply remain.
- **Rollback test baseline.** The rollback test compares against a database migrated to version 5, not against hard-coded literals. "As before" is defined by the real previous state, and this avoids a second copy of the vocabulary.
- **`role` gets no pattern.** `stores_data_in.role` is a plain string. The issue says "string, a database role name" and the validator supports no pattern keyword.
- **`protocol` enum order.** The issue doesn't fix the order. `postgres` and `otlp` go before `other`, as in [SPEC-model-03], so `other` stays last.
- **Graph check covers the traversal criterion.** "Impact and graph queries include it" is checked through `/graph` only, because no impact code exists in `arch-api` yet.

## Docs impact
None. [SPEC-model-02], [SPEC-model-03] and [SPEC-model-04] already describe the vocabulary this migration seeds (they cite hub issue #17). The `arch-api` README lists no individual types, so it needs no change.

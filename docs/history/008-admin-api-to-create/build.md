STATUS: READY

# Build: Admin API for node and edge types

## Summary
- arch-api now has six admin-only operations under `/api/v1/admin/types` (create, update, delete for node types and edge types). Each runs in one transaction and writes exactly one `change_log` row (`entity = 'type'`, `entity_key` `node/<id>` / `edge/<id>`).
- Schemas must use the documented subset (`validateSchema`). Secret-like property names give `422 /problems/secret-detected`. Before a schema or `allowed` change is applied, it is checked against every existing node or edge of the type (`409 /problems/conflict` with `count`). Built-in types can't be deleted or lose a property. A custom type that is still in use can't be deleted (`409 /problems/in-use` with `count`).
- `GetNodeType` and `GetEdgeType` now take `FOR SHARE`, so node and edge writes and type changes are serialised on the type row. An integration test shows a node insert waiting for a type change and then being checked against the new schema.
- arch-web only regenerates `src/api/schema.d.ts`.
- Round 2: both branches are rebased onto `origin/main`, which now includes arch-api#7 (migration 00006), arch-api#8 (migration 00007, `source` taken from the actor) and arch-web#6. Type writes go through `record()`, so their change_log `source` is `ui` for users and `api` for service accounts. Force-pushed with lease. Draft PRs: CliXiD/arch-api#9 and CliXiD/arch-web#7.

## Changes
### arch-api
- `internal/db/queries/write.sql` and the regenerated `internal/db/dbq/write.sql.go`: `GetNodeType` and `GetEdgeType` now take `FOR SHARE`.
- `internal/db/queries/types.sql` and the generated `internal/db/dbq/types.sql.go` add these queries:
  - create, lock (`FOR UPDATE`), update and delete for each type table;
  - `CountNodesOfType` and `CountEdgesOfType`;
  - `ListNodeAttributesOfType`;
  - `ListEdgesOfType`, which returns the from and to kinds and the attributes of each edge, so one pass counts each failing edge once.
- `internal/model/types.go`:
  - adds `NodeTypeCreate`, `NodeTypePatch`, `EdgeTypeCreate` and `EdgeTypePatch`, with Huma tags for `pattern`, the kind `enum`, `minLength`, `minItems`, `uniqueItems` and `nullable:"false"`;
  - the `Change.EntityKey` doc now names the type keys.
- `internal/model/errors.go`:
  - adds the `ErrBuiltin` sentinel and `IncompatibleError{Count}`;
  - the `InUseError` doc and message now cover nodes or edges.
- `internal/model/validate.go`: new `validateSchema`. It returns at most one error per location, sorted by location, with fixed messages. Errors sit at `body.attributes_schema`, `.properties.<name>`, `.properties` (empty name) or `.required`.
- `internal/model/secrets.go`: new `checkSchemaSecrets`. It reuses `secretName` and `secretNameToken` and returns a `*SecretError` with locations only.
- `internal/model/types_write.go` (new) adds `Create`, `Update` and `Delete` for `NodeType` and `EdgeType`, all in `s.inTx`:
  - **Updates:** lock the row, validate the schema, check for secrets, check built-in property loss, then run the existing-data check. When nothing changes (`sameJSON`), nothing is written.
  - **Deletes:** map an FK violation to `InUseError`, using a re-count taken outside the aborted transaction.
- `internal/model/write.go`: adds the `entityType = "type"` constant. Since the rebase, the change_log `source` comes from main's `Actor.source()` through `record()`.
- `internal/httpapi/routes_types.go` (new) registers the six operations with role `Admin`, called from `registerRoutes` in `routes.go`. On PATCH and DELETE, the `409` response uses the `InUseProblem` schema.
- `internal/httpapi/routes_write.go`: the `Writer` interface gains the six methods.
- `internal/httpapi/routes_model.go` (`entityFailure`):
  - adds `conflictDetail` entries for node types and edge types;
  - `ErrBuiltin` maps to `409 /problems/conflict`, with detail `built-in types can't be deleted` for `delete-*` operations and `built-in types can't lose attributes` otherwise;
  - `IncompatibleError` maps to `InUseProblem` with type `/problems/conflict`, detail `existing nodes|edges would fail the change` and `count`;
  - the `InUseError` detail now depends on the entity (`edge type is still used by edges`).
- `internal/httpapi/api.go`: the `InUseProblem` and `count` docs now say "nodes or edges".
- `api/openapi.yaml`: regenerated with `make openapi`.
- Tests:
  - `internal/model/validate_test.go`: `TestValidateSchema`.
  - `internal/model/secrets_test.go`: `TestCheckSchemaSecrets`.
  - `internal/httpapi/routes_write_test.go`:
    - `fakeWriter` gains the six methods;
    - `TestWriteRoles` gains 18 cases;
    - `TestWriteRequestValidation` gains 12 cases;
    - new `TestTypeProblems` and `TestTypeSecretProblem`;
    - `TestWriteRoutesNeedAToken` gains 6 routes.
  - `cmd/arch-api/types_integration_test.go`: new `TestTypeWriteIntegration`. In round 2 it gained two subtests:
    - `every seeded schema is in the subset`: re-sends every stored type's schema (and `allowed`) as admin, expects 200, and expects no change_log row;
    - `a service account's type write records source api`.
  - `internal/model/validate_test.go` (round 2): `TestValidateSchema` gained the two schemas seeded by migration 00006 (`calls` with `path`, `stores_data_in` with `port`/`role`).
- `README.md`:
  - six rows in the Endpoints table;
  - the `type` entity and its `entity_key` in Writes;
  - a **Types** bullet;
  - the type 404 and 409 rows in the problem table;
  - `specs/008_admin.md` added to Documents.

### arch-web
- `src/api/schema.d.ts`: regenerated with `pnpm gen:api` from the job's arch-api worktree. No other files changed.

## Acceptance criteria
1. [x] [arch-api] Create `message-broker`, list it, editor 403, repeat 409: `TestTypeWriteIntegration/create_a_node_type` passes. It checks the 201 body, `builtin: false` in `GET /api/v1/types`, the editor's `/problems/forbidden`, and the repeat's `/problems/conflict` with detail `a node type with this id already exists`.
2. [x] [arch-api] On a node type with nodes, adding a required attribute gives 409 with `count` 2 (one node in `prod`, one in `dev`). Adding an optional attribute gives 200 with the new schema. A narrower enum gives 409 with `count` 1. Evidence: subtest `a_node_type_schema_change_is_checked_against_existing_nodes`.
3. [x] [arch-api] On edge type `publishes_to`, with two application→infrastructure edges:
   - dropping the pair from `allowed` gives 409 with `count` 2;
   - an edge that fails both the pair and the schema check is counted once;
   - a schema-only change gives `count` 1;
   - keeping the pair and adding another gives 200.

   Evidence: subtest `an_edge_type_allowed_change_is_checked_against_existing_edges`.
4. [x] [arch-api] Built-in and delete rules, evidence in subtests `built-in_types` and `deletes`:
   - `DELETE node-types/service` and `DELETE edge-types/calls` give 409 `/problems/conflict` with no `count`;
   - a `calls` PATCH without `port` gives 409 `built-in types can't lose attributes`;
   - a `calls` PATCH that adds `timeout_ms` to the stored schema gives 200;
   - renaming `service` gives 200;
   - deleting unused custom types gives 204, and they are gone from `GET /types`; a second delete gives 404;
   - deleting `message-broker` (2 nodes) gives 409 `/problems/in-use` with `count` 2;
   - deleting `publishes_to` (2 edges) gives `edge type is still used by edges` with `count` 2.
5. [x] [arch-api] An `api_key` property gives 422 `/problems/secret-detected` with exactly one error, at `body.attributes_schema.properties.api_key`. The body contains none of the submitted name, enum value, id or other property name. Evidence: subtest `secrets_and_schema` and `go test -count=1 -run TestCheckSchemaSecrets ./internal/model` (pass).
6. [x] [arch-api] These all give 422 `/problems/validation` with the field path: an object property, the `pattern` keyword, `required` naming an undeclared property, id `Message_Broker`, kind `planet`, a `planet` kind in `allowed` (`body.allowed[0].to`), and `kind` in a PATCH. Evidence: `go test -count=1 -run TestValidateSchema ./internal/model` (pass, 33 cases) and the integration subtests.
7. [x] [arch-api] change_log rows:
   - each subtest asserts its exact type rows (key, action, actor, source `ui`) via `changesSince`;
   - the final assertion lists exactly the 10 successful type writes;
   - no-op PATCHes (same body, `{}`) add no row;
   - the rejected 403, 404, 409 and 422 writes add no row (`changeCount` unchanged);
   - the `before` and `after` JSON is checked on the create and the delete;
   - `source` is `ui` for the admin user and `api` for an admin service account (round 2).
8. [x] [arch-api] Viewer and editor get 403 on all six operations, and admin succeeds: `go test -count=1 -run TestWriteRoles ./internal/httpapi` passes. The integration subtest `viewers_and_editors_can't_write_types` also checks this against the DB.
9. [x] [arch-api] `grep -c "admin/types" api/openapi.yaml` gives 4 (the four paths). All six operation ids are present, and `make openapi-check` passes.
10. [x] [arch-api] `grep -n "admin/types\|node/<id>" README.md` shows the six Endpoints rows (lines 111-116) and the `node/<id>` / `edge/<id>` entity_key in Writes (line 143).
11. [x] [arch-web] The `grep` from criterion 11 finds `/api/v1/admin/types/node-types` (lines 42 and 59) and `create-edge-type` (lines 17 and 719). After the commit, re-running `pnpm gen:api` leaves `git diff --exit-code src/api/schema.d.ts` clean.

## Validation
Round 2, after the rebase onto `origin/main`:
- arch-api:
  - `factory/checks/arch-api.sh`: pass;
  - `go test -tags integration -count=1 ./...`: pass;
  - `go tool golangci-lint run --build-tags integration ./...`: 0 issues.
- arch-web:
  - `factory/checks/arch-web.sh`: pass;
  - `pnpm gen:api` followed by `git diff --exit-code src/api/schema.d.ts`: clean.

Round 1:
- arch-api: `FACTORY_HUB=… FACTORY_REPO_KEY=arch-api FACTORY_BASE=main bash factory/checks/arch-api.sh` passed (go vet, golangci-lint with 0 issues, go test, go build, make openapi-check).
  - `go test -tags integration -count=1 ./...` passed on podman, including the existing `TestWriteIntegration` and `TestModelIntegration`, so the `FOR SHARE` change breaks nothing.
  - `go tool golangci-lint run --build-tags integration ./...` reported 0 issues.
- arch-web: `bash factory/checks/arch-web.sh` passed (lint, typecheck, vitest 30/30, build).

## Log
### Round 2
- **Feedback 1** (the user accepts the three open decisions in decision.md: `entity_key` `node/<id>|edge/<id>`, the full type JSON in audit rows, `FOR SHARE` on type reads): no code change needed for these.
- **Rebase, arch-api:** `git rebase origin/main`. The only conflict was in `README.md`, in two places:
  - the Writes paragraph now has main's `source` text (`ui` for a user token, `api` for a service account) plus `type` and its `entity_key`;
  - the Permissions bullet now has main's unknown-owner sentence plus "Teams, environments and types are admin-only".

  `make sqlc` and `make openapi` produced no diff after the rebase, so the generated files match their sources.
- **Main's actor-derived source:** type writes call `record(ctx, q, a, ...)`, which now uses `a.source()`, so no code change was needed. A new integration subtest checks that a service-account admin's create and delete record `source = api`.
- **New seed and migration version 7:**
  - `TestValidateSchema` gained 00006's schemas;
  - a new integration subtest shows every seeded type (00003 and 00006) passes `validateSchema` and that re-sending it is a no-op;
  - the built-in `calls` patch already builds on the stored schema, which now includes `path`;
  - main's `TestWriteIntegration` asserts migration version 7 and passes.
- **Rebase, arch-web:** rebased onto `origin/main` with no conflict. `pnpm gen:api` from the rebased arch-api worktree left `src/api/schema.d.ts` unchanged.
- **Checks:**
  - `factory/checks/arch-api.sh`: pass;
  - `go test -tags integration -count=1 ./...`: pass;
  - `golangci-lint --build-tags integration`: 0 issues;
  - `factory/checks/arch-web.sh`: pass (lint, typecheck, vitest 30/30, build).
- Both branches force-pushed with `--force-with-lease`.


### Round 1
- Implemented the spec in `merge_order`: arch-api first, then arch-web regenerated from the arch-api worktree.
- arch-api commits:
  - fix: share-lock the type row while a node or edge write validates against it;
  - feat: add the admin type endpoints;
  - test: add the integration test;
  - docs: update the README;
  - test: build the built-in `calls` patch from its stored schema.
- Rebase notes for the open arch-api PRs:
  - CliXiD/arch-api#7 (migration 00006) gives `calls` a `path` property. The built-in-type integration test builds its PATCH from the stored `calls` schema, so it doesn't depend on the seed. The new seeded schemas in #7 stay inside the subset `validateSchema` accepts.
  - #7 and #8 touch `write.go`, `write.sql` and `openapi.yaml`. A rebase will need `make sqlc` and `make openapi` re-run, not hand-merged generated files.
  - #8 changes `source` to `api` for service writes. `record()` is shared, so type rows would follow that change.
- Choices within the spec:
  - The new operations use the existing `model` OpenAPI tag.
  - The secret-detected `detail` reuses the existing text, `attributes look like secrets`.
  - An empty property name is reported at `body.attributes_schema.properties`.
- No migration and no env or config change, so nothing is needed in arch-deploy. The `docs/` updates listed under Docs impact are left to the hub's docs step; the builder writes only build.md in the hub.

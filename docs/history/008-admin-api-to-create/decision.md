APPROVE

## Summary
- arch-api#9 adds six admin-only operations under `/api/v1/admin/types` to create, update and delete node and edge types. They cover schema-subset validation, secret-name rejection, checks against existing data (`409` with `count`), built-in protection, in-use delete protection, and one `change_log` row per write. arch-web#7 only regenerates `src/api/schema.d.ts`.
- Round 1 was escalated for one reason only: the job adds new `change_log` writes, which is on the Always escalate list. It asked the human three questions: the `entity_key` format `node/<id>|edge/<id>`, the full type JSON in audit rows, and `FOR SHARE` on type reads. The owner accepted all three in feedback-1 and asked for a rebase.
- Round 2 rebased both branches onto the current `origin/main`, which now includes arch-api#7 and #8 and arch-web#6. Only a README conflict needed fixing by hand. `make sqlc`, `make openapi` and `pnpm gen:api` produced no diff. Two integration subtests were added (seeded schemas stay in the subset; a service-account write records `source = api`).
- Round 2 gate: `GATE: PASS` for both repos. All four reviews are `VERDICT: PASS` with no findings, and none of the Notes describes a real problem.
- I checked it myself. Both branch heads are the gated commits and both contain `origin/main`. `TestTypeWriteIntegration` passes against PostgreSQL, with all 18 subtests green. The unit tests `TestValidateSchema`, `TestCheckSchemaSecrets`, `TestWriteRoles`, `TestTypeProblems` and `TestTypeSecretProblem` pass, and `make openapi-check` passes. Across repos, re-running `pnpm gen:api` against the arch-api worktree leaves `schema.d.ts` clean.

## Why
The only thing that needed a human was the new `change_log` writes, and the owner has already decided on all three points. Round 2 is a clean rebase that changes no security-relevant code: auth middleware, role mapping, grants, migrations and secret patterns are all untouched. The change stays inside intake's Scope and REPOS, adds no migration, dependency or env var, and every acceptance criterion is met with tests I re-ran.

## Acceptance criteria
1. [arch-api] Admin creates `message-broker` (201, listed with `builtin: false`); editor gets 403; a repeat gets 409 `/problems/conflict`: met. I re-ran the integration subtest `create_a_node_type` and it passes.
2. [arch-api] A required attribute on a type with nodes gives 409 with the right `count`; an optional one gives 200: met. The subtest `a_node_type_schema_change_is_checked_against_existing_nodes` passes, and I read the per-node count in `UpdateNodeType`.
3. [arch-api] Dropping a used allowed pair gives 409 with `count`; keeping it and adding one gives 200: met. The subtest `an_edge_type_allowed_change_is_checked_against_existing_edges` passes.
4. [arch-api] Built-in delete or property loss gives 409; adding a property gives 200; an unused custom delete gives 204; a used one gives 409 `/problems/in-use` with `count`: met. The subtests `built-in_types` and `deletes` pass, and I read `losesProperty` and `ErrBuiltin` in `types_write.go`.
5. [arch-api] `api_key` gives 422 `/problems/secret-detected` with only the field path: met. `TestCheckSchemaSecrets`, `TestTypeSecretProblem` and the subtest `secrets_and_schema` pass. `checkSchemaSecrets` reuses `secretName` and `secretNameToken`, so the patterns are unchanged.
6. [arch-api] A schema outside the subset, a bad id or an unknown kind gives 422 `/problems/validation` with the path: met. `TestValidateSchema` passes, and so do the 7 integration cases.
7. [arch-api] Exactly one `change_log` row per successful write, and none for a no-op or a rejected write: met. This is asserted through `changesSince` in the integration test, which passes. `source` follows main's `record()`: `ui` for users, `api` for service accounts.
8. [arch-api] Viewer and editor get 403 on all six operations: met. `TestWriteRoles` passes, and all six are registered with `register(..., Admin, ...)` in `routes_types.go`.
9. [arch-api] `openapi.yaml` has the 4 paths and 6 operation ids: met. `make openapi-check` passes, and the gate log shows the same.
10. [arch-api] The README lists the six operations and the `node/<id>` / `edge/<id>` keys: met (README diff, build.md).
11. [arch-web] `schema.d.ts` has the new paths and operations, and regenerating it gives no diff: met. I ran `pnpm gen:api`, and `git diff --exit-code src/api/schema.d.ts` is clean.

## Merge order
1. CliXiD/arch-api#9: merge and deploy first. It owns the contract, and the change is additive.
2. CliXiD/arch-web#7: `schema.d.ts` regenerated from the merged `api/openapi.yaml`.
3. arch-deploy: no change.

## Docs impact
- `docs/specs/008_admin.md` Interfaces: replace `POST|PATCH|DELETE /api/v1/types/node[/{id}]` and `/api/v1/types/edge[/{id}]` with `POST /api/v1/admin/types/{node-types|edge-types}` and `PATCH|DELETE .../{id}` (admin only). Mark the type endpoints as shipped (hub issue #19).
- `docs/specs/003_editing-history.md` [SPEC-editing-history-06]: state the `entity_key` for types (`node/<id>` / `edge/<id>`), which the owner accepted in feedback-1.
- `docs/adr/0016-append-only-change-log-as-built.md`: add `type node/<id> | edge/<id>` to the `entity_key` list.
- `docs/specs/002_model.md` [SPEC-model-03]: list the exact accepted keywords (`enum`, `minimum`/`maximum`, `items: {type: string}`, `required`, `additionalProperties`). Add that a type whose schema uses anything else is rejected with `422`.

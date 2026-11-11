ESCALATE

## Summary
- arch-api adds one new goose migration, `migrations/00006_model_vocabulary.sql`. It adds the built-in node types `client`, `load-balancer`, `container-registry` and `job`, and appends `external → application` to `calls` and `depends_on`. It also widens the `calls` schema (`postgres` and `otlp` added to the protocol enum, a new `path` attribute) and the `stores_data_in` schema (new `port` and `role` attributes).
- No Go behaviour, sqlc output or `api/openapi.yaml` changes. The rest of the diff is tests: version pins move to 6, "seeded vocabulary" is updated, a new "wider vocabulary" write subtest is added, and `TestMigrationVocabularyRollback` checks Up then Down against a real version-5 snapshot.
- Round 1 gate: `GATE: PASS`. The code and db reviews both say `VERDICT: PASS`, with no findings, and their notes describe no real problem.
- The change matches [SPEC-model-02], [SPEC-model-03] and [SPEC-model-04], which already cite hub issue #17. It stays inside intake's scope (arch-api only).
- It is escalated only because it is a schema migration that changes data, which the approver rules always send to a human.

## Why
The work is correct and complete. I checked the Down literals in 00006 against 00003 character by character, and they match. Up only inserts rows and updates rows by id, and it drops or renames nothing. Still, any new migration that changes data must be merged by a person, so the factory doesn't auto-merge it even though `arch-api` allows auto-merge.

## Acceptance criteria
1. [arch-api] 00006 exists with Up and Down, and it is the only file changed under `migrations/`: met. `git diff --stat origin/main...HEAD` shows only `migrations/00006_model_vocabulary.sql` under migrations.
2. [arch-api] `GET /api/v1/types` lists the four new types with their kinds and `builtin: true`: met. The Up INSERT has the right ids, kinds, names and `builtin = true`, and build.md reports the "seeded vocabulary" subtest (18 types) passing.
3. [arch-api] `calls` and `depends_on` from a client to an application give 201, and the `calls` edge is in `/graph?environment=prod`: met. I spot-checked this in the diff: the "wider vocabulary" subtest posts browser (client) → payments-api for both edge types expecting 201, then asserts the `calls` edge appears in the graph. build.md reports it passing.
4. [arch-api] `otlp` + `path` gives 201, `smtp` gives 422 at `body.attributes.protocol`: met. The same subtest covers both, and the new `calls` schema literal matches the spec.
5. [arch-api] `stores_data_in` with `{5432, arch_app}` gives 201, `port: 70000` gives 422 at `body.attributes.port`: met. The same subtest asserts both results and the stored attributes.
6. [arch-api] Up to 6 then Down one step gives version 5 and the version-5 vocabulary: met. `TestMigrationVocabularyRollback` compares `to_jsonb` snapshots, and I confirmed the Down literals equal 00003.
7. [arch-api] Existing writes behave as before and the full integration suite passes: met per build.md. The later subtests' counts were adjusted for the extra rows, not weakened.
8. [arch-api] `TestEmbeddedMigrations` expects 6 and `make openapi-check` shows no diff: met. checks.md shows unit tests and openapi-check passing, and no files under `api/`, `internal/model`, `internal/httpapi` or `dbq` changed.

## Merge order
1. CliXiD/arch-api#7. arch-web and arch-deploy have no change.
2. On deploy, the Helm migrate job applies version 6 before the new pods roll out ([ADR-0009]). Old pods report `/readyz` 503 until they are replaced, as with every migration.

## Docs impact
None. [SPEC-model-02], [SPEC-model-03] and [SPEC-model-04] already describe this vocabulary.

## For the human
Please confirm that migration `00006_model_vocabulary.sql` can be merged and deployed, then merge CliXiD/arch-api#7.

- **What it does:** inserts 4 built-in rows into `node_types` and updates 3 rows in `edge_types` (`calls`, `depends_on`, `stores_data_in`). Nothing is dropped or renamed.
- **What Down does:** restores the exact 00003 values, then deletes the 4 types. If nodes already use one of the new types, the foreign key makes Down fail on purpose, so no data is deleted.
- **Files to look at:** `migrations/00006_model_vocabulary.sql` and `cmd/arch-api/migrate_integration_test.go` in CliXiD/arch-api#7.
- **One thing to check:** the db reviewer didn't run the migration and only read the SQL. build.md says the builder ran the integration suite (podman), including the rollback test, and it passed. If you want independent proof, run `go test -tags integration -count=1 ./cmd/arch-api/` on the PR branch before merging.

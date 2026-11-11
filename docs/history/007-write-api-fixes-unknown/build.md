STATUS: READY

# Build: Write API fixes: unknown owner 422, `api` source, kind-pair location

## Summary
- An unknown `owner` on node create, or on an owner change, now returns `422 /problems/validation` with a single error at `body.owner` ("team does not exist"). The check runs inside the transaction, before the team-membership check.
- Writes made with a service-account token record `source: api` on the node or edge and on every `change_log` row (`Actor.source()`). User tokens keep `ui`. The new migration `00007_source_api.sql` widens the three `source` CHECK constraints. It only expands them: no backfill.
- A disallowed kind pair on `POST /api/v1/edges` is reported at `body.from` when no allowed pair of that edge type starts at the source node's kind, and at `body.to` otherwise.
- `api/openapi.yaml` has `api` in all three `source` enums, and arch-web's `src/api/schema.d.ts` is regenerated from it.
- Round 2: the branch is rebased onto main, which now includes CliXiD/arch-api#7 (`00006_model_vocabulary.sql`). This job's migration is renumbered to `00007`, and the latest-version assertions now expect 7. PRs: CliXiD/arch-api#8 and CliXiD/arch-web#6 (both drafts).

## Changes
### arch-api
- `migrations/00007_source_api.sql` (new): `Up` drops and re-adds `nodes_source_check`, `edges_source_check` and `change_log_source_check` with `('ui', 'api', 'yaml', 'discovery', 'import')`. `Down` restores the four-value checks, with a comment that it fails once any `api` row exists.
- `internal/db/db_test.go`: `TestEmbeddedMigrations` now expects latest version 7.
- `internal/db/queries/write.sql`: in `CreateNode`, `UpdateNode`, `CreateEdge` and `UpdateEdge`, the `'ui'` literal is replaced with `sqlc.arg('source')`. `internal/db/dbq/write.sql.go` is regenerated with `make sqlc`.
- `internal/model/write.go`:
  - New `sourceAPI` constant and `Actor.source()` (`service` → `api`, otherwise `ui`).
  - `record()` and the four node/edge writes use `a.source()` for both the stored source and the returned one.
  - New helper `checkOwner` (TeamExists → `ValidationErrors{{body.owner, "team does not exist"}}`).
  - `CreateNode` runs `checkOwner` first inside the transaction, then `a.can`. `UpdateNode` runs lock → `can(cur.Owner)` → (on an owner change) `checkOwner` → `can(new)` → version check.
  - Both old "unknown team" blocks are removed.
- `internal/model/types.go`: the three `source` enum tags now include `api`. `api/openapi.yaml` is regenerated with `make openapi`.
- `internal/model/validate.go`: `checkKindPair` returns `body.from` when no allowed pair has `From == fromKind`, otherwise `body.to`. The message is unchanged.
- `internal/model/validate_test.go`: `TestCheckKindPair` is now table-driven, with 4 cases (allowed; calls infra→app → body.from; calls app→infra → body.to; runs_on app→network → body.to).
- `internal/model/write_test.go` (new): `TestActorSource`, table-driven (`service` → `api`, `user` → `ui`).
- `cmd/arch-api/write_integration_test.go`:
  - The readiness check expects version 7.
  - New edge cases: `eks-prod → payments-api` gives `body.from` and checks the message; `payments-api → eks-prod` gives `body.to`.
  - Unknown owner on POST, as editor and as admin, and unknown owner on PATCH of `eks-prod`. All of these sit inside "rejected writes leave no row", so the test also proves no `change_log` row is written.
  - "service account writes" now asserts `source api` on the PATCH row. It also creates node `ci-built` (response `api`, history entry `api`/`service`), creates an edge (`api`), then deletes the node and asserts both delete rows are `api`. Deleting the node keeps the later counts unchanged.
  - The "history" test expects `api` for the arch-ci-platform entry and `ui` for every other entry.
- `README.md` "Writes" now documents: `source` is `ui` for a user token and `api` for a service account; an unknown owner gives `422 body.owner` before the membership check; the kind pair is reported at `body.from` or `body.to`.

### arch-web
- `src/api/schema.d.ts`: regenerated with `ARCH_API_OPENAPI=../arch-api/api/openapi.yaml pnpm gen:api` from this job's arch-api worktree. The only diff is `"api"` added to the three `source` unions.

## Acceptance criteria
1. [x] [arch-api] Unknown owner on POST as editor and as admin: `TESTCONTAINERS_RYUK_DISABLED=true go test -tags integration -count=1 ./cmd/arch-api/ -run TestWriteIntegration` passes. The subtests `rejected_writes_leave_no_row/unknown_owner_as_editor` and `/unknown_owner_as_admin` assert 422, `/problems/validation`, `locations()==["body.owner"]` and the message "team does not exist", and the enclosing test asserts `changeCount` is unchanged.
2. [x] [arch-api] PATCH with an unknown owner: the subtest `owner_changed_to_an_unknown_team` sends PATCH `/api/v1/nodes/prod/eks-prod` with `If-Match: "1"` and `{"owner":"no-such-team"}`, and gets the same 422 at `body.owner`.
3. [x] [arch-api] Source by token type, covered by `service_account_writes`:
   - The service token creates `ci-built`: the response has `source: api`, and the history create entry has `source: api` and `actor_kind: service`.
   - An edge created by the service token has `source: api`.
   - The editor-created `payments-api` returns `ui` (`create_nodes`), and its history entries are `ui` (`history`).
4. [x] [arch-api] Kind pair on `POST /api/v1/edges`: `calls` from `eks-prod` to `payments-api` gives 422 at `["body.from"]` with the message `edge type calls does not allow infrastructure → application`. `calls` from `payments-api` to `eks-prod` gives 422 at `body.to`.
5. [x] [arch-api] `go test -count=1 ./internal/model/ -run 'TestCheckKindPair|TestActorSource' -v` passes: 4 kind-pair cases (covering both `body.from` and `body.to`) and 2 source cases.
6. [x] [arch-api] `git diff --stat origin/main -- migrations/` lists only the new `00007_source_api.sql` (it was `00006` in the spec; renumbered because job 006 took `00006`, as the spec's Assumptions allow), which holds the three `ADD CONSTRAINT ..._source_check CHECK (source IN ('ui', 'api', 'yaml', 'discovery', 'import'))` statements.
7. [x] [arch-api] `grep -c "'ui'" internal/db/queries/write.sql` prints 0. `grep -c -- "- api$" api/openapi.yaml` prints 3. `make openapi-check` passes.
8. [x] [arch-api] README "Writes" mentions `api` for service accounts, `body.from` for the kind pair, and `team does not exist` at `body.owner` (lines 136, 152, 158).
9. [x] [arch-web] `grep -c '"ui" | "api" | "yaml" | "discovery" | "import"' src/api/schema.d.ts` prints 3, and `git diff --stat origin/main` lists only `src/api/schema.d.ts`.

## Validation
- arch-api:
  - `FACTORY_HUB=… FACTORY_REPO_KEY=arch-api FACTORY_BASE=origin/main bash factory/checks/arch-api.sh` passed (vet, golangci-lint 0 issues, unit tests, build, openapi-check).
  - `TESTCONTAINERS_RYUK_DISABLED=true go test -tags integration -count=1 ./...` passed in every package.
  - With plain podman, testcontainers' reaper fails ("network bridge not found"), so Ryuk is disabled for local runs.
  - Round 2, after the rebase and the renumbering: the arch-api gate passed (0 lint issues, openapi-check clean), and the full integration suite passed, including job 006's `TestMigrationVocabularyRollback`.
  - Round 2: `make sqlc` and `make openapi` produced no diff.
- arch-web: `FACTORY_HUB=… FACTORY_REPO_KEY=arch-web FACTORY_BASE=origin/main bash factory/checks/arch-web.sh` exits 0 (lint, typecheck, 30 tests, build).
  - Round 2: re-running `pnpm gen:api` against the rebased `openapi.yaml` produced no diff, and nothing in arch-web changed.

## Log
### Round 1
- Implemented the spec in arch-api: migration, queries plus sqlc regeneration, the source helper, the owner-check order, the kind-pair location, the OpenAPI regeneration, unit and integration tests, and the README.
- Regenerated arch-web's schema from the branch's `openapi.yaml`.
- Updated `TestEmbeddedMigrations` and the integration readiness check to expect version 6. The spec did not list these, but both assert the latest migration version.
- To keep the later "in use" counts valid, the service-created node is deleted at the end of "service account writes" (this also covers the cascaded deletes recording `api`).
- Open coordination point: CliXiD/arch-api#7, not yet merged, also adds a `00006`. If it merges first, this job's migration must be renumbered to `00007`, and the two version-6 assertions changed to 7, during a rebase onto `origin/main`.
- Opened draft PRs CliXiD/arch-api#8 and CliXiD/arch-web#6 and linked them to each other. Not done in this job: the ADR-0016 note listed under Docs impact, which is a hub docs edit and out of scope here.
- High risk (change_log constraints, the order of the permission check): a human signs off.

### Round 2
- Feedback-1 asked for this job to be rebased. `factory/bin/job rebase` had already rebased the branch onto main, which now includes CliXiD/arch-api#7 (job 006, `00006_model_vocabulary.sql`).
- Renamed `migrations/00006_source_api.sql` to `00007_source_api.sql`. Changed the latest-version assertions in `internal/db/db_test.go` and the integration readiness check from 6 to 7.
- Folded both changes into the original migration and test commits with fixup plus autosquash, so the history never shows a second `00006`. Force-pushed with lease.
- Checked that job 006's tests and this job's tests agree:
  - Job 006 adds `external → application` to `calls`. `calls` from `eks-prod` (infrastructure) still reports `body.from`.
  - The node counts and source assertions are unchanged, and the full integration suite passes.
  - `TestMigrationVocabularyRollback` (Up to 6, then Down) still passes with 7 present.
- Generated files: `make sqlc` and `make openapi` produced no diff. arch-web's `schema.d.ts` still matches `openapi.yaml`, so arch-web needed no change this round.
- Updated the PR #8 body: it now names migration `00007` and notes the rebase.
- The human sign-off from decision.md is still needed: the `change_log` constraint, `record()` writing `api`, and the ADR-0016 note after merge.

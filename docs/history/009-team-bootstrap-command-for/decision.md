ESCALATE

## Summary
- arch-api gains `arch-api teams add <id> --name <name>`. It runs as the schema owner (`MIGRATE_DATABASE_URL`, falling back to `DATABASE_URL`) and creates a team plus its `change_log` row through the existing `CreateTeam`/`record`, which this job does not change. The actor is `system` / `arch-api teams add` / `service` and the source is `api`.
- The command is idempotent ("already exists" exits 0). Input is validated before any config is read. Database errors are cut down to a fixed message plus an optional SQLSTATE, so the DSN never reaches the output.
- Gate PASS on e856aa2. The code, db and security reviews all PASS with no findings. All 9 acceptance criteria are met, and there is no OpenAPI, migration, sqlc, dependency or deploy change.
- I'm escalating only because of policy. This is a new writer of `change_log` rows, and it creates teams outside the admin-only API with owner privileges. The Factory notes list `change_log` writes under Always escalate, and teams are part of access control.

## Why
The build is clean and matches the spec. I spot-checked it: the unit tests pass, and `teams add Bad_Id --name x` with no database variables set exits 1 with the slug message. The Always escalate list covers "changes to `change_log` grants or writes", and this job adds a new path that writes audit rows under a new service identity. That path also bypasses the role check [SPEC-admin-04] puts on team creation, and team ids drive authorization through the Keycloak `teams` claim. So a human should confirm that an owner-credential CLI is an acceptable way to create teams and write audit rows.

## Acceptance criteria
1. [arch-api] Create on an empty migrated DB: exits 0, `GET /api/v1/teams` lists `platform`, and there is one change_log row with actor `system`, actor_name `arch-api teams add`, kind `service`, source `api`, entity `team`, action `create`, before NULL. Met: `TestTeamsAddIntegration/creates_the_team_and_one_change_log_row` (podman run, build.md), and the test code asserts every one of these values.
2. [arch-api] A re-run exits 0 with "already exists", writes no second row and keeps the name. Met: integration subtest; `ErrConflict` rolls back inside `inTx`.
3. [arch-api] `Bad_Id` exits 1 with the slug message and writes nothing. Met: `TestRun` row plus the integration subtest. I also checked it by hand (exit 1, exact message, no DB vars set).
4. [arch-api] A blank `--name` exits 1 with `teams add: --name must not be empty`. Met: `TestRun` row.
5. [arch-api] Missing or invalid config gives `config: DATABASE_URL is required` / `config: MIGRATE_DATABASE_URL is invalid`, exit 1. Met: `TestRun` rows.
6. [arch-api] The DSN never appears in output. Met: `TestTeamsAddUnreachableDatabase` (runs in the gate) checks the DSN, user, password, host and db name. The integration helper asserts the same on every run. In the code, `teamsAddDBError` never prints `err`.
7. [arch-api] `model.IsSlug`/`SlugPattern` exist, with a reflection test against the three `pattern` tags. Met: `internal/model/slug_test.go`, which passes. I re-ran it.
8. [arch-api] The usage lists `teams add`, and openapi/migrations/dbq are unchanged. Met: the diff stat touches only 7 files (none of those), and `make openapi-check` passes in the gate.
9. [arch-api] README (Run it, Configuration, Database roles, Layout) and `.env.example` mention `teams add`. Met: per the diff and build.md.

## Merge order
1. CliXiD/arch-api#10 (`factory/009-team-bootstrap-command-for` into `main`). Blocker #18 (`00007_source_api.sql`) is already on `main`. No other repos.

## Docs impact
- `docs/specs/009_operations.md` Interfaces: add `arch-api teams add <id> --name <name>` to the subcommands, and note that `MIGRATE_DATABASE_URL` (owner) is used by `migrate` and `teams add`.
- `docs/specs/008_admin.md` [SPEC-admin-04]: one sentence saying operators can create a team without a login using `arch-api teams add` (owner role, idempotent, change_log source `api`), while the API stays admin-only.
- `docs/adr/0014-separate-database-roles-for-migrations-and-runtime.md`: a Consequences line saying the owner connection is also used by `teams add`.

## For the human
Please decide whether to merge CliXiD/arch-api#10. The code, tests and reviews are clean. It is here only because it is on the Always escalate list (`change_log` writes) and touches access (creating teams outside the admin-only API).

To confirm:
1. Is it acceptable for a team to be created with the owner credential (`MIGRATE_DATABASE_URL`), without any role check? Whoever holds that credential can create teams, just as they can already run `migrate`.
2. Is the audit row shape acceptable: actor `system`, actor_name `arch-api teams add`, actor_kind `service`, source `api`? It is written by the unchanged `record()` in the same transaction.
3. Is it fine that a re-run with a different `--name` reports "already exists" and doesn't change the name?

Files to look at: `cmd/arch-api/main.go` (`parseTeamsAdd`, `teamsAdd`, `teamsAddDBError`), `cmd/arch-api/teams_integration_test.go` and `internal/model/slug.go`.

Optional follow-up (out of scope here): `arch-api migrate` still prints the raw pgx error, which can include `host=... user=...`. The security review recommends a separate issue for it.

After merge, update the three hub documents listed under Docs impact.

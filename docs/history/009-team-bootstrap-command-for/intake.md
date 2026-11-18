DECISION: ACCEPT
RISK: high
SURFACES: security
REPOS: arch-api
RESCOPED: no

## Summary
- Accepted as written: a new `arch-api teams add <id> --name <name>` subcommand in `arch-api` only; no endpoint, OpenAPI, schema or deploy change.
- The blocker (#18) has landed: `migrations/00007_source_api.sql` already allows `source = 'api'` on `change_log`.
- The existing `model.Service.CreateTeam` already writes the team and its `change_log` row in one transaction, and the `Actor` type already maps `Kind: "service"` to `source: api`, so the command is a thin CLI over code that exists.
- Risk is high only because it writes the `change_log` (a High-risk area) and connects as the schema owner; the change itself is small.
- Connection-string handling follows `migrate` (per Decision 4 and [ADR-0014]): `MIGRATE_DATABASE_URL`, falling back to `DATABASE_URL`.

## Scope
**arch-api**

- New subcommand `arch-api teams add <id> --name "<name>"`, dispatched from `cmd/arch-api` next to `serve`, `migrate` and `seed`, listed in the usage text and in the README (run-it section, configuration table, layout).
- Configuration exactly like `migrate` (`config.LoadMigrate`): `MIGRATE_DATABASE_URL`, else `DATABASE_URL`. When neither is set it prints `config: DATABASE_URL is required` style output naming the variable and exits 1; when the value is not a valid connection string it says the variable is invalid. Values are never printed (this is the behaviour [ADR-0014] and [SPEC-operations-05] already describe, and the sensible reading of Decision 4 "like `migrate`"; Behaviour 5 is satisfied because the missing variable is always named).
- Input validation before any connection: `<id>` must match the slug `^[a-z0-9][a-z0-9-]{1,62}$` ([SPEC-model-05]; today that pattern only lives in Huma struct tags, so the command needs the same rule in Go, ideally shared), and `--name` must be non-empty after trimming. A failure prints the reason to stderr and exits 1 with nothing written.
- On success it creates the team and, in the same transaction, one `change_log` row with `actor` `system`, `actor_name` `arch-api teams add`, `actor_kind` `service`, `source` `api`, `entity` `team`, `entity_key` `<id>`, `action` `create`, `before` null, `after` the team JSON — i.e. `Service.CreateTeam` called with `Actor{Subject: "system", Username: "arch-api teams add", Kind: "service"}`. Prints `team <id> created`, exit 0.
- If the team exists (`ErrConflict` from the unique violation) it prints `team <id> already exists`, writes no row, exits 0. The existing team's name is not compared or changed.
- Any database error exits 1 with a message that never includes the connection string, host, user or password: pgx connect errors embed `host=... user=...`, so the command must not print the raw error (print a short fixed message, optionally the SQLSTATE). A test asserts stdout and stderr never contain the DSN.
- Tests: unit tests for argument parsing, slug and name validation, missing/invalid variable and exit codes in `cmd/arch-api`; integration-tagged tests (existing testcontainers helpers) for create, re-run idempotence (exactly one `change_log` row), invalid id writes nothing, and the "no DSN in output" assertion.

**Left out** (as the issue says): rename/delete from the CLI, any Helm or `arch-deploy` wiring, any API or OpenAPI change, `arch-web`. Spec 009's interface list (`arch-api migrate up|status`) should gain the new subcommand when the job is recorded; that's a docs follow-up, not part of the build.

## Why
`repos/arch-api/internal/model/write.go` already has `CreateTeam` writing the team and its `change_log` row via `record()` in one `inTx`, and `Actor.source()` returns `api` for `Kind == "service"`, so the requested row shape is reachable without touching the write path or the schema. `config.LoadMigrate` already implements the owner-role connection string with the documented fallback, and `cmd/arch-api/main.go` is a plain `switch` on args that the new case slots into. Nothing in the BRD, specs or ADRs contradicts the issue; the `api` source the issue depends on was added by #18 (`migrations/00007_source_api.sql`), so the "Blocked by" is cleared.

## Questions
None.

## Research
None.

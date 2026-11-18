# `arch-api teams add`: create the first teams without a login

> Issue #20: Team bootstrap command for a fresh database

## Summary
- Adds one operator subcommand, `arch-api teams add <id> --name <name>`, so a freshly migrated database can get its teams without an interactive admin login. Today only an admin can create a team, through the API ([SPEC-admin-04]).
- It runs as the schema owner via `MIGRATE_DATABASE_URL` (falling back to `DATABASE_URL`, exactly like `migrate`, [ADR-0014]). It reuses `model.Service.CreateTeam`, so the team and its `change_log` row are written in one transaction ([SPEC-editing-history-06]) with a fixed `service` actor and source `api`.
- It is idempotent. An existing team counts as success and writes nothing, so deploy scripts can re-run it.
- It never prints a connection string. Database errors are reduced to a fixed message.
- arch-api only. No endpoint, OpenAPI, schema, migration or deploy change. The team API stays admin-only.

## Context
- `arch-api:cmd/arch-api/main.go` has `run(args, stdout, stderr) int`, a plain `switch` over `args` that dispatches `serve`, `migrate up|status` and `seed --sample`. It also holds the `usage` constant (printed with exit `2` for any unknown shape) and the package doc comment that lists the subcommands. `seedSample` is the pattern for a subcommand body: load the config, `db.NewPool(dsn, false)`, call a `model` function, map the errors to fixed messages, print one result line.
- `arch-api:cmd/arch-api/main_test.go` has the table-driven `TestRun` (args, env, want code, want stderr substring). It runs without a database.
- `arch-api:internal/config/config.go`: `LoadMigrate(getenv)` returns `Migrate{DatabaseURL}`. It reads `MIGRATE_DATABASE_URL`, else `DATABASE_URL`, and fails with `*config.Error` (`config: DATABASE_URL is required` / `config: <NAME> is invalid`). That error names the variable and never its value.
- `arch-api:internal/db/db.go`: `NewPool` returns `db.ErrInvalidURL` (which never carries the URL) on a parse failure. The pool is lazy: a connection failure only shows up on the first query. pgx connect errors include `host=... user=...`, and `migrate` prints its raw error (`"migrate:", err`). The new command must not copy that.
- `arch-api:internal/model/write.go`: `(*Service).CreateTeam(ctx, Actor, TeamCreate) (Team, error)` inserts the team and calls `record(...)` (entity `team`, key = id, action `create`, before `nil`, after the team JSON) inside `inTx`. A unique violation comes back as `model.ErrConflict` and the transaction rolls back, so no row is written. `Actor.source()` returns `api` when `Kind == "service"`. `model.NewService(pool)` builds the service.
- `arch-api:internal/model/types.go`: `Actor{Subject, Username, Kind, Admin, Teams}`. `TeamCreate{ID, Name}` carries the slug rule only as a Huma struct tag, `pattern:"^[a-z0-9][a-z0-9-]{1,62}$"` ([SPEC-model-05]). No Go regexp for it exists today.
- `arch-api:migrations/00007_source_api.sql` (from #18) already allows `change_log.source = 'api'`. The owner role can `INSERT` into `change_log`, and the append-only trigger only blocks UPDATE/DELETE/TRUNCATE ([ADR-0014], [SPEC-editing-history-08]).
- Integration helpers in `arch-api:cmd/arch-api/integration_test.go` (`startPostgres` returns owner and `arch_app` DSNs, plus `newPool` and `newEngine`) and in `arch-api:cmd/arch-api/write_integration_test.go` (`changeCount`, `changesSince`, `lastChangeID`). They sit behind the `integration` build tag.
- `arch-api:README.md` covers this command in three places: the "Run it" block, the Configuration table (`MIGRATE_DATABASE_URL` → "used by `migrate`") and the Layout line for `cmd/arch-api`. `arch-api:.env.example` has the comment "Used by `migrate` only; defaults to DATABASE_URL."

## Contract
Single repo; no contract.

For reference, the CLI interface this job adds (from the issue's Contract):
```
arch-api teams add <id> --name <name>
  env:    MIGRATE_DATABASE_URL (owner), else DATABASE_URL
  stdout: "team <id> created\n" | "team <id> already exists\n"
  exit:   0 created or already exists
          1 invalid id or name, missing/invalid config, database error
          2 malformed invocation (usage), as for every other subcommand
```

## Requirements

### arch-api

1. **Dispatch.** `run` gets a new case for `args[0] == "teams" && args[1] == "add"`. The remaining arguments must be exactly one positional `<id>` plus the flag `--name <name>` (also accepted as `--name=<name>`), in either order. Any other shape prints `usage` to stderr and returns `2`, like the existing cases: no `--name`, a second positional, an unknown flag, `teams` alone, or `teams` followed by anything other than `add`. The `usage` constant gains the line `arch-api teams add <id> --name <name>   create a team if it is missing (MIGRATE_DATABASE_URL, else DATABASE_URL)`. The package doc comment lists the new subcommand.
2. **Input validation first.** The id and name are checked before any config is read and before any connection is made:
   - The id must match `^[a-z0-9][a-z0-9-]{1,62}$`. Otherwise stderr gets `teams add: id must be a slug matching ^[a-z0-9][a-z0-9-]{1,62}$` and the exit code is `1`.
   - The name must be non-empty after `strings.TrimSpace`. Otherwise stderr gets `teams add: --name must not be empty` and the exit code is `1`.
   - When both fail, the id message comes first. Both are printed, and the exit code is `1`.
3. **Shared slug rule.** Add one exported Go form of the slug rule in `internal/model`: a `SlugPattern` constant with the pattern text and an `IsSlug(string) bool` function using a compiled regexp. The command uses it. A unit test in `internal/model` checks two things. First, it checks `IsSlug` on table cases: `platform`, `a1`, a 63-character slug and `core-banking` are valid; `Bad_Id`, `-x`, `a`, a 64-character string, an uppercase string and the empty string are not. Second, it uses reflection to check that the `pattern` tags of `TeamCreate.ID`, `EnvironmentCreate.ID` and `NodeCreate.ID` equal `SlugPattern`, so the two forms cannot drift. The struct tags themselves are not changed, so `api/openapi.yaml` is unchanged.
4. **Configuration.** After validation the command calls `config.LoadMigrate(os.Getenv)`, unchanged. On error it prints that error (`config: DATABASE_URL is required`, `config: MIGRATE_DATABASE_URL is invalid`, ...) to stderr and exits `1`. No new env var and no new config type are added.
5. **Write.** The command opens `db.NewPool(cfg.DatabaseURL, false)` (closed on return) and calls `model.NewService(pool).CreateTeam(ctx, model.Actor{Subject: "system", Username: "arch-api teams add", Kind: "service"}, model.TeamCreate{ID: id, Name: name})`. The name is passed exactly as given, not trimmed. The actor values are named constants in `cmd/arch-api`. Neither `CreateTeam` nor `record` is changed. The resulting `change_log` row has `actor = system`, `actor_name = arch-api teams add`, `actor_kind = service`, `source = api`, `entity = team`, `entity_key = <id>`, `action = create`, `before` NULL, and `after` the team JSON.
6. **Outcomes.**
   - Success prints `team <id> created` to stdout and exits `0`.
   - `errors.Is(err, model.ErrConflict)` prints `team <id> already exists` to stdout and exits `0`. Nothing is written, and the existing team's name is neither compared nor changed.
   - Any other error, from `NewPool`, connecting or the transaction, prints `teams add: database error` to stderr and exits `1`. When the error wraps a `*pgconn.PgError`, ` (SQLSTATE <code>)` is appended. The raw error text is never printed or logged: it can hold the host, user or password.
7. **No secrets in output.** stdout and stderr never contain the connection string or any part of it (user, password, host, port, database name), on any path.
8. **Unit tests** (no build tag; they run in the gate), added as rows to `TestRun` or as a new table-driven test in `cmd/arch-api/main_test.go`:
   - Malformed shapes return exit `2` with `usage:`: `teams`, `teams remove x`, `teams add`, `teams add platform`, `teams add platform --name`, `teams add a b --name x`, `teams add platform --name x --force`.
   - `teams add Bad_Id --name x` returns `1` with the slug message, even with no database variables set, which shows validation runs before config.
   - `teams add platform --name "  "` returns `1` with the empty-name message.
   - With `DATABASE_URL` and `MIGRATE_DATABASE_URL` both empty, `teams add platform --name Platform` returns `1` with `config: DATABASE_URL is required`.
   - With `MIGRATE_DATABASE_URL=postgres://arch:dummy-pw@[::1` (invalid), it returns `1` with `config: MIGRATE_DATABASE_URL is invalid`.
   - With `MIGRATE_DATABASE_URL=postgres://dummy-user:dummy-pw@127.0.0.1:1/dummy-db?sslmode=disable&connect_timeout=2` (unreachable), it returns `1`, stderr contains `teams add: database error`, and neither stdout nor stderr contains the DSN, `dummy-user`, `dummy-pw`, `127.0.0.1` or `dummy-db`.
   - `--name=Platform` is accepted the same as `--name Platform`. This can be covered by the parser unit test when the parsing lives in its own function.
9. **Integration tests** in a new file `cmd/arch-api/teams_integration_test.go` (`//go:build integration`), using `startPostgres`, `newPool`, `newEngine` and the change_log helpers:
   - On a freshly migrated database with `MIGRATE_DATABASE_URL` set to the owner DSN, `run([]string{"teams","add","platform","--name","Platform"}, ...)` returns `0` with stdout `team platform created\n`. `GET /api/v1/teams`, served by the engine over the `arch_app` pool with a viewer token, lists `{id: platform, name: Platform}`. Exactly one new `change_log` row exists, with the values of requirement 5.
   - Running it a second time with `--name Other` returns `0` with stdout `team platform already exists\n`. The `change_log` count is unchanged, and the team's name is still `Platform`.
   - `teams add Bad_Id --name x` returns `1`. The team count and `change_log` count are unchanged.
   - When `MIGRATE_DATABASE_URL` is unset and `DATABASE_URL` holds the owner DSN, `teams add core --name Core` returns `0`, which proves the fallback.
   - On every run above, stdout and stderr do not contain the owner DSN or its password.
10. **Docs in the repo.**
    - `README.md` "Run it": add `go run ./cmd/arch-api teams add platform --name "Platform"  # create a team if missing (MIGRATE_DATABASE_URL)`, followed by one short paragraph. The paragraph covers: idempotent (`already exists`, exit `0`); invalid id or empty name exits `1` and writes nothing; the `change_log` row with actor `system` / `arch-api teams add`, kind `service`, source `api`; team ids must match the Keycloak group names ([SPEC-identity-access-05]); the team API stays admin-only.
    - `README.md` Configuration table: `MIGRATE_DATABASE_URL` is used by "`migrate`, `teams add` (as the schema owner)", and `DATABASE_URL`'s fallback note names `teams add` as well.
    - `README.md` Database roles: the Owner bullet says it runs `migrate` and `teams add`.
    - `README.md` Layout: `cmd/arch-api` lists `teams add`.
    - `.env.example`: the `MIGRATE_DATABASE_URL` comment becomes "Used by `migrate` and `teams add` only; defaults to DATABASE_URL."

## Acceptance criteria
1. [arch-api] On an empty migrated database, `teams add platform --name "Platform"` exits 0 and prints `team platform created`. `GET /api/v1/teams` then lists `platform`. Its single `change_log` row has actor `system`, actor_name `arch-api teams add`, actor_kind `service`, source `api`, entity `team`, entity_key `platform`, action `create` and before NULL. Verify with `cd <arch-api worktree> && go test -tags integration -count=1 -run TeamsAdd ./cmd/arch-api/` (needs podman or docker). The test of requirement 9 must pass.
2. [arch-api] Running it again (any `--name`) exits 0 and prints `team platform already exists`. It writes no second `change_log` row and leaves the name unchanged. Verified by the same integration test.
3. [arch-api] `teams add Bad_Id --name x` exits 1 with `teams add: id must be a slug matching ^[a-z0-9][a-z0-9-]{1,62}$` on stderr and writes nothing. Verify the message and exit code with `go test -count=1 -run TestRun ./cmd/arch-api/`, and the nothing-written part with the integration test.
4. [arch-api] `teams add platform --name "  "` exits 1 with `teams add: --name must not be empty`. Verify with `go test -count=1 -run TestRun ./cmd/arch-api/`.
5. [arch-api] With no `MIGRATE_DATABASE_URL` and no `DATABASE_URL`, `teams add platform --name Platform` exits 1 with `config: DATABASE_URL is required`. With an unparsable `MIGRATE_DATABASE_URL` it exits 1 with `config: MIGRATE_DATABASE_URL is invalid`. Verify with the unit tests in `cmd/arch-api`.
6. [arch-api] Output and errors never contain the database URL. Against an unreachable DSN the unit test asserts exit 1, `teams add: database error`, and no DSN, user, password, host or database name in stdout or stderr. The integration test asserts the same for the owner DSN. Verify with `go test -count=1 ./cmd/arch-api/` and the integration run above.
7. [arch-api] `model.IsSlug` and `model.SlugPattern` exist. A test in `internal/model` asserts that `SlugPattern` equals the `pattern` tag of `TeamCreate.ID`, `EnvironmentCreate.ID` and `NodeCreate.ID`. Verify with `go test -count=1 ./internal/model/`.
8. [arch-api] Running `go run ./cmd/arch-api` with no arguments prints a usage that includes `arch-api teams add <id> --name <name>`. `git diff main -- api/openapi.yaml migrations/ internal/db/dbq/` is empty.
9. [arch-api] `README.md` mentions `teams add` in "Run it", the Configuration table (`MIGRATE_DATABASE_URL` row), Database roles and Layout. `.env.example` says `MIGRATE_DATABASE_URL` is used by `migrate` and `teams add`. Verify with `grep -n "teams add" README.md .env.example`.

## Merge and deploy order
One PR in arch-api. Its blocker #18 (`00007_source_api.sql`) is already on `main`. No other repo changes.

## Out of scope
- Renaming, deleting or listing teams from the CLI. Adding `--update`, or changing the name of an existing team.
- Any change to the team API, its roles or the auth middleware (Decision 2).
- Seeding teams from a migration (Decision 1), or changing `seed --sample`.
- Any Helm, `arch-deploy`, hub `dev/` or compose wiring, such as a job or a hook that runs `teams add`.
- Any change to `config.LoadMigrate`, `db.Migrate`, `model.CreateTeam`, `record`, the change_log schema or its grants. No new migration.
- Fixing `migrate`'s own raw error output. It is tempting, but it is not this job.
- arch-web, and any OpenAPI regeneration.
- Changing the Huma `pattern` struct tags to reference the new constant. Tags must stay literals, and the OpenAPI must not change.

## Assumptions
- **Exit `2` for a malformed invocation.** The issue's contract lists only 0 and 1, but every existing subcommand prints the usage and exits `2` when its shape is wrong (README: "Any other command prints the usage and exits `2`"). Exit `1` stays for an invalid id or name, missing config and database errors, as the issue says. A missing `--name` flag is a malformed invocation (`2`); `--name ""` is an empty name (`1`).
- **Missing-variable message.** It is `config: DATABASE_URL is required`, the `LoadMigrate` wording, even though the command prefers `MIGRATE_DATABASE_URL`. Decision 4 says "like `migrate`", and intake's binding scope says the same. This message names the variable the fallback ends at, which meets Behaviour 5.
- **Validation before config.** An invalid id fails even without any database variable. Intake's scope puts validation before any connection, and checking input first is the cheapest path.
- **Name stored as given, not trimmed.** This matches the API, which stores `name` as received. Only the emptiness check trims.
- **Existing team, different name.** The command reports `already exists` and does not compare or change the name. Intake made this call, and Decision 3 (idempotent re-runs) is satisfied.
- **Fixed database error message with an optional SQLSTATE.** This is the only way to guarantee no host, user or password leaks from pgx errors ([NFR-001]). The SQLSTATE gives operators something to act on.
- **Actor `Admin: false`, `Teams: nil`.** `CreateTeam` does no role check (the API layer does), so the flag is irrelevant. Leaving it false keeps the actor minimal.
- **Escalation.** This adds a new writer of `change_log` rows and runs as the schema owner. Both are on the Always-escalate / High-risk lists, so the approver should expect a human to look at it. The write path itself (`record`) is reused unchanged.

## Docs impact
- `docs/specs/009_operations.md` Interfaces: the subcommand line becomes `arch-api migrate up|status`, `arch-api teams add <id> --name <name>`. The env line says `MIGRATE_DATABASE_URL` (owner) is used by `migrate` and `teams add`.
- `docs/specs/008_admin.md` [SPEC-admin-04]: add one sentence. Operators can create a team without a login using `arch-api teams add` (owner role, idempotent, change_log source `api`); the API stays admin-only.
- `docs/adr/0014-separate-database-roles-for-migrations-and-runtime.md`: add a Consequences line saying the owner connection (`MIGRATE_DATABASE_URL`) is also used by `teams add`. The decision itself is unchanged.

STATUS: READY

# Build: `arch-api teams add`: create the first teams without a login

## Summary
- New subcommand `arch-api teams add <id> --name <name>` (also `--name=<name>`, either order). It runs as the schema owner via `MIGRATE_DATABASE_URL`, else `DATABASE_URL` (`config.LoadMigrate`, unchanged).
- It validates the id and name before reading config, then calls `model.Service.CreateTeam` with the fixed actor `system` / `arch-api teams add` / `service`. The team and its `change_log` row (source `api`) are written in one transaction.
- It is idempotent: `ErrConflict` prints `team <id> already exists` and exits 0. Database errors print only `teams add: database error`, plus ` (SQLSTATE <code>)` when the error wraps a `*pgconn.PgError`.
- New `model.SlugPattern` / `model.IsSlug`, with a reflection test that keeps them equal to the `pattern` tags of `TeamCreate`, `EnvironmentCreate` and `NodeCreate`. The tags themselves are unchanged and so is the OpenAPI.
- Draft PR: https://github.com/CliXiD/arch-api/pull/10

## Changes
### arch-api
- `internal/model/slug.go` (new): the `SlugPattern` constant and `IsSlug` (compiled regexp).
- `internal/model/slug_test.go` (new): the table of `IsSlug` cases (valid: `platform`, `a1`, 63 chars, `core-banking`; invalid: `Bad_Id`, `-x`, `a`, 64 chars, `PLATFORM`, empty) and the reflection test on the three `pattern` tags.
- `cmd/arch-api/main.go`: the package doc and `usage` line for `teams add`, the actor constants (`teamsAddSubject`, `teamsAddUsername`, `teamsAddKind`), the `teams add` dispatch case (any malformed shape prints usage and exits 2), `parseTeamsAdd` (exactly one positional plus one `--name`; duplicates, unknown or `-` flags, and a missing value are rejected), `teamsAdd` (validation, config, pool, `CreateTeam`, outcomes) and `teamsAddDBError` (fixed message plus optional SQLSTATE).
- `cmd/arch-api/main_test.go`: `TestRun` rows for every malformed shape in requirement 8 (exit 2), the usage line, invalid id with no DB vars, blank name, both invalid (both messages, id first), missing config and invalid `MIGRATE_DATABASE_URL`. Also new `TestParseTeamsAdd` (covers `--name=` and either order) and `TestTeamsAddUnreachableDatabase` (exit 1, fixed message, no DSN, user, password, host or database name in stdout or stderr).
- `cmd/arch-api/teams_integration_test.go` (new, `integration` tag): `TestTeamsAddIntegration` covers create plus API listing plus one `change_log` row with all the requirement 5 values (`before` NULL, `after` the team JSON), the re-run with `--name Other` (already exists, no new row, name kept), `Bad_Id` (no team or change written) and the `DATABASE_URL` fallback. Every run asserts that stdout and stderr contain neither the owner DSN nor its password.
- `README.md`: the "Run it" line and paragraph, the Configuration table (`DATABASE_URL` fallback and `MIGRATE_DATABASE_URL` rows), the Database roles Owner bullet and Layout.
- `.env.example`: the `MIGRATE_DATABASE_URL` comment.

No other repo in the job.

## Acceptance criteria
1. [x] [arch-api] On a migrated DB, `teams add platform --name "Platform"` exits 0 with `team platform created`, `GET /api/v1/teams` (arch_app pool, viewer token) lists it, and there is one change_log row with the expected values: `go test -tags integration -count=1 -run TeamsAdd ./cmd/arch-api/` passes (podman; `TestTeamsAddIntegration/creates_the_team_and_one_change_log_row`).
2. [x] [arch-api] A re-run with `--name Other` exits 0 with `team platform already exists`, the change_log count is unchanged and the name is still `Platform`: same integration run, subtest `a_second_run_...`.
3. [x] [arch-api] `teams add Bad_Id --name x` exits 1 with the slug message: `TestRun` row "teams add with an invalid id and no database" (DB vars empty, so validation runs before config). The integration subtest `an_invalid_id_writes_nothing` shows the team and change_log counts unchanged.
4. [x] [arch-api] `--name "  "` exits 1 with `teams add: --name must not be empty`: `TestRun` row "teams add with a blank name".
5. [x] [arch-api] No DB vars gives `config: DATABASE_URL is required`, and an unparsable `MIGRATE_DATABASE_URL` gives `config: MIGRATE_DATABASE_URL is invalid` (both exit 1): `TestRun` rows.
6. [x] [arch-api] No DSN in output: `TestTeamsAddUnreachableDatabase` (unit, in the gate) checks the unreachable DSN and its parts. The integration helper asserts on every run that the owner DSN and `:<password>@` are absent.
7. [x] [arch-api] `model.IsSlug` and `model.SlugPattern` exist, and `TestSlugPatternMatchesTags` checks them against the three tags: `go test -count=1 ./internal/model/` passes.
8. [x] [arch-api] `go run ./cmd/arch-api` prints a usage that includes `arch-api teams add <id> --name <name>` (exit 2, output checked by hand and by a `TestRun` row). `git diff origin/main --stat -- api/openapi.yaml migrations/ internal/db/dbq/` is empty, and `make openapi-check` passes.
9. [x] [arch-api] `grep -n "teams add" README.md .env.example` finds hits in Run it (block and paragraph), the Configuration table (both DB rows), Database roles, Layout and `.env.example`.

## Validation
### arch-api
- `FACTORY_HUB=... FACTORY_REPO_KEY=arch-api FACTORY_BASE=origin/main bash factory/checks/arch-api.sh`: passes (vet, golangci-lint 0 issues, unit tests, build, openapi-check). The first run failed lint with gosec G602 (slice index in the parser) and G101 (a DSN literal assigned in the test). I fixed both by restructuring the code, without `nolint`.
- `go tool golangci-lint run --build-tags integration ./cmd/...`: 0 issues.
- `DOCKER_HOST=<podman socket> TESTCONTAINERS_RYUK_DISABLED=true go test -tags integration -count=1 ./...`: all packages pass, including `TestTeamsAddIntegration`.

## Log
### Round 1
- Implemented the spec in 4 commits (slug rule, command plus unit tests, integration test, docs), pushed `factory/009-team-bootstrap-command-for` and opened draft PR CliXiD/arch-api#10 against `main`.
- A note for the approver: this adds a new writer of `change_log` rows that runs as the schema owner. That is on the High-risk / Always-escalate lists, as the spec's Assumptions say. `record` and `CreateTeam` are unchanged.
- Hub docs impact (`docs/specs/009_operations.md`, `docs/specs/008_admin.md`, ADR-0014) is listed in the spec. Builders don't edit hub docs, so I left them unchanged.

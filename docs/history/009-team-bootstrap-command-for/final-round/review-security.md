VERDICT: PASS

## Summary
- arch-api gains an operator-only CLI subcommand, `teams add <id> --name <name>`. It runs as the schema owner via `MIGRATE_DATABASE_URL`, falling back to `DATABASE_URL`. There is no new endpoint, and the team API and auth middleware are unchanged.
- The id is validated against the shared slug rule, and the name must be non-empty after trimming. Both checks run before any config is read or connection opened, and there is no raw SQL: the write goes through the existing sqlc-backed `CreateTeam`.
- The `change_log` row is written by the unchanged `record` path in the same transaction, with a fixed `system` / `service` actor and source `api`. No grants or migrations change.
- Database errors are reduced to a fixed message plus an optional SQLSTATE. Unit and integration tests assert that no DSN, user, password, host or database name reaches stdout or stderr ([NFR-001]).
- No new dependencies (`pgconn` is already in the module) and no secrets in the commits. `.env.example` changes only a comment.

## Findings
None.

## Notes
- The approver should send this to a human. It adds a new writer of `change_log` rows that runs with owner privileges, which is on the High-risk / Always-escalate lists. The write path itself (`CreateTeam`, `record`) is reused unchanged and is correct.
- The CLI bypasses Huma validation, so it enforces the id rule itself (`model.IsSlug`, kept in sync with the struct tags by a reflection test). It is stricter than the API on the name (trimmed non-empty versus `minLength:"1"`). Neither path caps the name's length, so this is no worse than the API.
- The command trusts whoever holds the owner DSN, which is intended: access control is possession of the owner credential, the same as for `migrate`.
- Pre-existing, not changed here: `migrate` still prints its raw error, which can include pgx's `host=... user=...` text. The spec scopes this out on purpose, but it is worth a follow-up issue.
- `ErrConflict` reflects any unique violation from the team insert. For `teams` that is only the primary key, so "already exists" is accurate.

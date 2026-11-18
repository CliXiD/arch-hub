VERDICT: PASS

## Summary
- Adds `arch-api teams add <id> --name <name>`, which writes through the unchanged `model.CreateTeam` as a fixed `service` actor, so the team and its `change_log` row (source `api`) go in one transaction.
- Input is validated before config is read. Idempotency (`ErrConflict` prints "already exists", exit 0) and exit codes 0/1/2 match the spec.
- Database errors are reduced to a fixed message plus an optional SQLSTATE, so the DSN cannot leak. Unit and integration tests assert this.
- New `model.SlugPattern` and `IsSlug`, with a reflection test against the three `pattern` tags. The OpenAPI, migrations and sqlc output are untouched.
- README and `.env.example` are updated in all the places the spec lists. The commits are small and conventional.

## Findings
None.

## Notes
- This adds a new `change_log` writer that runs as the schema owner. Both are on the Always-escalate list, so a human should look at it, as the spec says.
- `parseTeamsAdd` rejects any argument starting with `-` as an id, which matches the spec's "unknown flag" rule.

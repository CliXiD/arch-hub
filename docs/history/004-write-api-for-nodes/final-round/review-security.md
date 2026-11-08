VERDICT: PASS

## Summary
- arch-api adds 12 write operations and `GET /history`. Every operation goes through `register()` with a minimum role (Editor for nodes and edges, Admin for teams and environments, Viewer for history), so `accessMiddleware` guards all of them. No unauthenticated endpoint is added.
- Team scoping in `internal/model/write.go` matches [SPEC-identity-access-05]. Admins can write anything. Anyone else needs the node's owner team, both teams for an owner change, and the source node's team for an edge. Each check runs on the row after it is locked with `FOR UPDATE` and before the version check.
- `change_log` is append-only at two layers. `arch_app` gets only SELECT and INSERT, and a trigger rejects UPDATE, DELETE and TRUNCATE even for the owner. Rows are written in the same transaction as the change, through one helper.
- Secrets and model values stay out of responses and logs. Validation and secret messages are fixed text, `newProblem` still clears `errors[].value`, and a 500 logs only the operation and `error_class` (SQLSTATE or Go type). Every query is parameterised through sqlc.
- No new dependency and no committed credentials (only the dummy `arch`/`arch_app` test passwords). arch-web changes only the generated `src/api/schema.d.ts`.

## Findings
None.

## Notes
- **Always escalate applies to this job.** It adds `change_log` writes and grants (`migrations/00004_change_log.sql`, `00005_app_role_grants.sql`, `internal/model/write.go` `record`) and touches `internal/auth/principal.go`. The auth change only adds the `Username` field: role mapping, token validation and `accessMiddleware` are unchanged, and I found no problem in it. These still need a human approver.
- `arch-api:internal/model/write.go` `lockEdgeFor` reads the source node's owner with `NodeOwnerKind`, which takes no lock. A concurrent owner change on that node could race with an edge PATCH or DELETE. The impact is small, because either owner is a team the editor was allowed to act for a moment earlier. A `FOR SHARE` read would close the gap if wanted.
- `arch-api:internal/model/secrets.go` userinfo regex `[^\s/@:]*:[^\s/@]+@` misses passwords that contain `/` or `@` (e.g. `postgres://u:p/w@h`). It meets the spec's stated patterns. Widening it is a pattern change, which is on the escalate list, so I suggest a follow-up only.
- `/history` shows viewers the full `before`/`after` JSON, attributes included, and the actor's token `sub`. This matches what viewers can already read through the GET endpoints and what the spec asks for. Attribute names, never values, appear in `errors[].location`.
- The CORS change (`engine.go`: allow the `If-Match` header, expose `ETag`) is harmless. Allowed origins are still the configured list.
- Pre-existing, unchanged: the trigger can be dropped or disabled by the owner role `arch`. That is expected under [ADR-0014], where the server runs as `arch_app`. The hub follow-up to switch `dev/env/arch-api.env` to `arch_app` is still open.

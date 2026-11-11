DECISION: ACCEPT
RISK: high
SURFACES: security
REPOS: arch-api, arch-web
RESCOPED: no

## Summary
- Accepted as written: three small write-API fixes in `arch-api`, plus a regenerated `schema.d.ts` in `arch-web`.
- The hub documents already carry the decisions: [BR-004] and [SPEC-model-08] list `api`, [SPEC-model-04] has the `body.from`/`body.to` rule.
- The code confirms each edge: `CreateNode` checks the owner's team membership before the team-exists check; `write.sql` and `record()` hardcode `source = 'ui'`; `checkKindPair` always returns `body.to`.
- Risk is high because it adds a migration that re-creates CHECK constraints on `change_log` (Always escalate: a human signs off, as Decision 4 says) and reorders a permission check.
- No UI change: `arch-web` only regenerates its API types; nothing in `src/` reads `source` today.

## Scope

**arch-api**

1. **Unknown owner is a 422.** `POST /api/v1/nodes` and `PATCH /api/v1/nodes/{environment}/{id}` (when `owner` changes) check that the owner team exists before checking the caller's membership of it. A missing team gives `422 /problems/validation` with one error `{location: "body.owner", message: "team does not exist"}`, for editors and admins alike. The existing in-transaction check (`unknown team` at `body.owner`, which today only admins ever reach) is replaced by this one; the current-owner permission check on PATCH stays first.
2. **`source: api` for service accounts.** Every node and edge write, and its `change_log` row, records `source: api` when the token is a service account (`actor_kind: service`, as `internal/auth` already decides) and `source: ui` for a user. The hardcoded `'ui'` in the create/update queries becomes a parameter (sqlc regenerated); the Huma `source` enums on node, edge and history entry gain `api`; `api/openapi.yaml` is regenerated. A new goose migration widens the `source` CHECK constraints on `nodes`, `edges` and `change_log` to `ui, api, yaml, discovery, import` (expand only, no backfill, no grant changes). Sample seed keeps `import`.
3. **Kind-pair error location.** On `POST /api/v1/edges`, a disallowed `(from kind, to kind)` reports at `body.from` when the source node's kind is not the `from` of any allowed pair of that edge type, otherwise at `body.to`. Message unchanged (`edge type X does not allow A → B`).
4. Tests for the three behaviours (unit and integration: `arch-ci-platform` token gives `api`, `editor` gives `ui`; `calls` from `infrastructure` → `body.from`, application → `infrastructure` → `body.to`). README "Writes" section updated (`source`, kind-pair location, 422 for unknown owner).

**arch-web**

- Regenerate `src/api/schema.d.ts` from the new `openapi.yaml` so the `source` unions include `"api"`. No other change.

**Left out** (per the issue): any UI showing the source; role or permission changes; YAML import. Note for the hub docs: [ADR-0016]'s "as built" column list still says `source ui|yaml|discovery|import`; the BRD and spec already include `api`, so a one-line note there is enough when the job merges.

## Why

`internal/model/write.go` runs `a.can(in.Owner)` before the transaction that calls `q.TeamExists`, so an editor with a typo gets `403 node is owned by team …` while an admin gets `422 unknown team`; moving the existence check first fixes both and, as Decision 1 says, leaks nothing a viewer can't read from `GET /teams`. `internal/db/queries/write.sql` writes `'ui'` as a literal and `record()` uses the constant `sourceUI`, while `internal/auth/principal.go` already sets `ActorKind = service`, so the source can be derived with no auth change. `checkKindPair` in `validate.go` already receives the `allowed` pairs, so choosing `body.from` or `body.to` is local. The three CHECK constraints live in migrations `00002` and `00004`, so a new migration is the only way to add `api`.

## Research

None.

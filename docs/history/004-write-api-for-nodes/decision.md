ESCALATE

## Summary
- arch-api adds the write side of the model: 12 write operations for nodes, edges, teams and environments; mandatory `If-Match` locking (`412`/`428`); attribute-schema and secret checks; and `GET /api/v1/history`. Every successful write adds one `change_log` row per entity in the same transaction.
- Two new migrations: `00004_change_log.sql` creates the append-only table and a trigger that rejects UPDATE, DELETE and TRUNCATE. `00005_app_role_grants.sql` gives the runtime role `arch_app` DML on the model tables and only SELECT and INSERT on `change_log`.
- arch-web only regenerates `src/api/schema.d.ts`.
- Round 1 shows `GATE: PASS` in both repos, and all four reviews (code, contract, db, security) are `VERDICT: PASS` with no findings. The builder also ran the integration tests and a local-stack run with real Keycloak tokens.
- The build itself looks correct. It still goes to a human because it is on the Always escalate list: it writes `change_log` and grants on it, adds a migration, and touches `internal/auth`.

## Why
The work matches the spec, and I would be comfortable merging the code. But Factory notes → Always escalate names "changes to `change_log` grants or writes". This job creates both, and it adds a schema migration with role grants. Those alone require a human. It also adds permission checks (team scoping), which count as access control, and a field on `auth.Principal`. The migration `00005` fails unless role `arch_app` already exists in the target database.

## Acceptance criteria
1. [arch-api] Only new migrations 00004/00005, with 00001-00003 untouched: met. I checked both files myself. The diff stat shows no change to the old migrations, and checks.md reports no protected paths changed.
2. [arch-api] An editor can create a node owned by `platform` (`201`, `ETag "1"`). Owner `core` gives `403` naming `core`, and a viewer gets `403`: met (integration `create_nodes`, unit `TestWriteRoles`, local stack).
3. [arch-api] Edge rights come from the source node's owner, and admin can do both directions: met. I read `CreateEdge` myself: it checks `a.can(from.Owner)`. Integration and local-stack evidence are in build.md.
4. [arch-api] The validation table returns the stated locations, and duplicates give `409 /problems/conflict`: met (unit `TestValidateAttributes`, `TestCheckKindPair`, `TestWriteRequestValidation`, plus the integration test).
5. [arch-api] Secret names and values give `422 /problems/secret-detected`, and no 6-character substring of a value appears in the body or logs: met (`TestSecretsAreNeverEchoed`, `TestCheckSecrets`).
6. [arch-api] Stale or `*` `If-Match` gives `412`, a missing one gives `428`, and the right version gives `200` with an ETag one higher: met (`TestPreconditions`, integration `optimistic_locking`).
7. [arch-api] Cascade delete gives `204`, both edges are gone, and exactly 3 rows are written: met. I read `DeleteNode` myself: it locks and deletes each edge with its own `record` call and then the node, all inside one `inTx`. The integration subtest confirms it.
8. [arch-api] A rejected write or a no-op PATCH leaves no row and keeps the version: met (integration).
9. [arch-api] History comes back newest first with before/after, `actor_kind` and `source: ui`. The cursor works, and `cursor=garbage` gives `422`: met (integration and local stack).
10. [arch-api] A service token records `actor_kind service`, with actor = actor_name = client id: met (unit `TestWriteActor`, integration, real `arch-ci-platform` token).
11. [arch-api] Deleting a team that owns nodes gives `409 in-use` with `count`. Creating and deleting environment `sandbox` gives `201`/`204`. Each write adds one row, and editors get `403`: met (integration and local stack).
12. [arch-api] As `arch_app`, UPDATE/DELETE fail with `42501`. As `arch`, the trigger rejects UPDATE/DELETE/TRUNCATE: met (integration `change_log is append-only`).
13. [arch-api] `migrate` uses `MIGRATE_DATABASE_URL`, and serve/seed use `DATABASE_URL`. Integration migrates as `arch` and serves as `arch_app`: met (config tests and the integration helpers).
14. [arch-api] Local stack: met, with a deviation. The builder used a throwaway database `arch_job004` on the running stack instead of `stack reset`, to keep the user's data. The intent (migrate as owner, serve as `arch_app`, `/readyz` 200) was covered.
15. [arch-api] Every operation has a minimum role, the openapi grep finds each path, and `make openapi-check` passes: met (gate log).
16. [arch-api] The README documents endpoints, If-Match, problems, `MIGRATE_DATABASE_URL` and the role prerequisite: met (README +109 lines).
17. [arch-web] The diff is only `src/api/schema.d.ts`, regenerated, with history present and typecheck passing: met. I checked that `git diff --stat` shows only that file and that `"/api/v1/history"` is at line 96. The contract review found it byte-identical to a fresh generation.

## Merge order
1. CliXiD/arch-api#5. Before its migrations run in any environment, role `arch_app` must exist there. Locally the hub init script creates it; on RDS no deploy slice provides it yet.
2. CliXiD/arch-web#5. If arch-api changes before merge, regenerate `schema.d.ts` again.
3. No arch-deploy change in this job.

## Docs impact
- [ADR-0014]: Status Proposed → Accepted (implemented here).
- [ADR-0005]: a new ADR superseding it (ADRs are append-only), with the spec 003 columns (`entity_key` instead of `entity_id`, `actor_name`, `environment` entity) and the trigger.
- `docs/specs/001_identity-access.md` Data: the `teams` claim matches `teams.id`, not `teams.name` (as [SPEC-admin-04] says).
- `docs/specs/003_editing-history.md` Data: add the `entity_key` formats and the edge-history expression indexes. Interfaces: add `428`, `409 /problems/in-use` and the `count` member. Also note that CORS now allows `If-Match` and exposes `ETag`.
- `docs/specs/008_admin.md` Interfaces: note that the team and environment write endpoints shipped with this slice (types still pending).
- Hub follow-up (not a document): after merge, switch `DATABASE_URL` in `dev/env/arch-api.env` to `arch_app`, as its comment and [ADR-0014] say.

## For the human
This job is on the Always escalate list. It adds `change_log` writes and grants plus a migration, and it touches `internal/auth`. The automated reviews found no problems, so what is needed is your sign-off on these points:

1. **Audit log and grants.** Review `migrations/00004_change_log.sql` (table, indexes, `change_log_reject()` trigger) and `migrations/00005_app_role_grants.sql` (`arch_app` grants) in CliXiD/arch-api#5. Also review the single `record` helper and the transaction boundaries in `internal/model/write.go`. Confirm the append-only design and the grant set are what you want.
2. **Rollout prerequisite.** `00005` fails with "role arch_app does not exist" in any database where that role isn't there. Locally the hub creates it. Decide whether merging before the deploy slice creates `arch_app` on RDS is acceptable, or whether to hold the merge until it does.
3. **Permissions.** Check the team-scoping rules in `internal/model/write.go` (`Actor.can`, owner change needs both teams, edges use the source node's owner, node delete cascades to other teams' edges without a check per issue Decision 5). Also check that `internal/auth/principal.go` only gains the `Username` field (role mapping and token validation are unchanged).
4. **Small follow-ups from the security review** (not blocking, you decide):
   - `lockEdgeFor` reads the source node's owner without `FOR SHARE`, so it could race with a concurrent owner change.
   - The userinfo secret regex misses passwords containing `/` or `@`. Changing it is a secret-pattern change, which is itself on the escalate list.
   - Names like `tokens_per_minute` are rejected as secrets.
5. **Unrequested addition.** `internal/httpapi/engine.go` now allows the `If-Match` header in CORS and exposes `ETag`. The browser SPA needs this to use the write contract. Confirm you're fine with it in this job.

After merge: merge arch-api#5 first, then arch-web#5. Then apply the Docs impact items above and switch `dev/env/arch-api.env` to `arch_app`.

DECISION: ACCEPT
RISK: high
SURFACES: security
REPOS: arch-api, arch-web
RESCOPED: no

## Summary
- Accepted as written: write endpoints for nodes, edges, teams and environments, attribute-schema and secret checks, team-based permission checks, `If-Match` locking, the append-only `change_log` with grants and trigger, the node history endpoint and the `MIGRATE_DATABASE_URL` split, all in `arch-api`; `arch-web` only regenerates `src/api/schema.d.ts`.
- The issue follows `003_editing-history.md`, `002_model.md` (SPEC-model-03/04/05/07/09/10), `001_identity-access.md` (SPEC-identity-access-05/07) and [ADR-0014]; the admin-only team/environment writes come from `008_admin.md` as Decision 1 says. Both blockers (#4, #7) are merged, so the model tables, sqlc, `register()` with `minRole`, and the `client_id == azp` service-account rule this slice relies on exist.
- Two document inconsistencies for the approver's Docs impact, not blocking: spec 001 Data says the `teams` claim matches `teams.name`, while spec 008, the seeded data (team id `platform`, realm group `platform`) and the issue match `teams.id`; [ADR-0005] still says `entity_id` and lacks `actor_name`/`environment`, which spec 003 has. The code decides both: the claim matches the team id.
- The slice is large but its parts cannot be separated usefully: [NFR-003] forbids any write without a `change_log` row, and a node needs an owner team to exist. The builder should keep the commits ordered (migration, validation, node/edge writes, team/environment writes, history, config).
- Risk is high: `change_log` grants and writes, a migration with a trigger and role grants, permission checks and secret detection are all under High risk and Always escalate. No research needed.

## Scope
Build the slice exactly as the issue's Behaviour, Decisions and Contract describe. Everything below is under `/api/v1`, RFC 9457 errors, through the existing `register()` with the stated minimum role.

**arch-api**
- New goose migration(s), never editing `00001`–`00003`: table `change_log` per spec 003 Data (`id bigserial`, `at`, `actor`, `actor_name`, `actor_kind user|service`, `source`, `entity node|edge|type|team|environment`, `entity_key`, `action create|update|delete`, `before jsonb`, `after jsonb`), index `(entity, entity_key, at desc)`, a trigger that raises on `UPDATE`, `DELETE` and `TRUNCATE`; grants to role `arch_app`: `SELECT, INSERT, UPDATE, DELETE` on the six model tables, `SELECT, INSERT` only on `change_log`, usage on the sequences. `arch_app` must exist before `migrate up` (the hub dev stack creates it in `dev/postgres/init/02-arch-app.sql`); the existing testcontainers integration test must create the role before migrating, and the README must say so.
- Config: `MIGRATE_DATABASE_URL` (optional, defaults to `DATABASE_URL`) read by `LoadMigrate`; `serve` and `seed` keep `DATABASE_URL`. Add it to `.env.example` with a comment. Values are never printed, as today.
- Node writes (editor): `POST /nodes` → `201` + `ETag: "1"`; `PATCH /nodes/{environment}/{id}` and `DELETE /nodes/{environment}/{id}` with mandatory `If-Match` (`428` missing, `412` stale); `id`, `type`, `environment` immutable in PATCH (`422`); changing `owner` needs rights on old and new team; delete cascades to every incoming and outgoing edge in one transaction, regardless of the other nodes' teams, one `change_log` row per deleted edge plus one for the node. PATCH responses carry the new `ETag`.
- Edge writes (editor, rights from the source node's owner): `POST /edges` → `201` + `ETag`, `PATCH /edges/{uid}` (`attributes` only), `DELETE /edges/{uid}`, same `If-Match` rules. Checks: allowed kind pair ([SPEC-model-04]), same environment ([SPEC-model-07]), duplicate `(environment, type, from, to)` → `409 /problems/conflict`.
- Validation on every node/edge write: attributes against the type's JSON Schema subset ([SPEC-model-03]: string, number, boolean, enum, array of string, required) → `422 /problems/validation` listing each bad field; slug check for ids; then the secret check of [SPEC-model-10] on attribute names and string values → `422 /problems/secret-detected` naming only the field path, value never in the body, the log or a trace. Keep the API's single 422 shape: the existing responses use Huma's `errors: [{ "location", "message" }]` with `value` cleared, so the issue's `path` is that `location` written as a path (`body.attributes.db_password`); do not introduce a second error shape.
- Permissions ([SPEC-identity-access-05]): editor may write nodes whose `owner` is in the token's `teams` claim (team ids) and edges whose source node they may write; admin may write anything; otherwise `403 /problems/forbidden` with the owning team id in `detail`. An unknown team in the claim grants nothing.
- Team and environment writes (admin): `POST/PATCH/DELETE /teams[/{id}]` (`id` slug, `name`), `POST/PATCH/DELETE /environments[/{id}]` (`id` slug, `name`, `sort`); duplicate id → `409 /problems/conflict`; delete while nodes reference it → `409 /problems/in-use` with `count`. No `If-Match` on these (the Contract does not ask for one).
- `change_log` writes happen in the service layer in the same transaction as the change ([ADR-0005]): `actor` = token `sub`, `actor_name` = `preferred_username` (for a service token the client id, per [SPEC-identity-access-07]), `actor_kind` from the principal, `source: ui`, `before`/`after` as full entity JSON (`null` on create/delete respectively). A no-op PATCH (same values) bumps nothing and writes no row; a failed write writes none.
- `GET /history?entity=node&environment=&id=&limit=&cursor=` (viewer): the node's rows and the rows of edges whose `from` or `to` is that node (including deleted edges), newest first, default limit 50, opaque cursor over `(at desc, id desc)`, `{ "items": [...], "next_cursor" }`. The spec writer must pin down how edge rows are found for a node efficiently at [NFR-005] scale (for example a jsonb expression index on `before`/`after` keys, or an indexed array of related node keys on `change_log`), since the issue's index alone only serves lookups by `entity_key`. Response values are model attribute values and need the viewer role like every read.
- Integration test (`//go:build integration`, testcontainers): as `arch_app`, `UPDATE`/`DELETE` on `change_log` fail with a permission error; as the owner, the trigger rejects `UPDATE`, `DELETE` and `TRUNCATE`; plus the transactional criteria (cascade delete gives three rows, failed write gives none). Stays out of the gate ([ADR-0010]).
- `make openapi` regenerated; `make openapi-check` passes; README documents the write endpoints, `If-Match`, the problems, `MIGRATE_DATABASE_URL` and the role requirement.

**arch-web**
- Regenerate `src/api/schema.d.ts` with `pnpm gen:api` from the merged `api/openapi.yaml`; `pnpm run typecheck` passes. No screen changes.

**Left out** (as the issue says): web forms and the History tab, type management and `/admin/*` screens, the global audit query, YAML import/export, any `arch-deploy` change (the repo is still empty; [ADR-0014] assigns `MIGRATE_DATABASE_URL` and the RDS role to the deploy slice).

**Docs and hub follow-ups for the approver:** mark [ADR-0014] Accepted; align [ADR-0005]'s column list with spec 003 (`entity_key`, `actor_name`, `environment` entity); fix spec 001 Data to say the `teams` claim matches `teams.id` (as [SPEC-admin-04] already does); after merge switch `DATABASE_URL` in `dev/env/arch-api.env` to `arch_app` as its comment and [ADR-0014] foresee. New Go dependencies (a JSON Schema validator, if one is used) will escalate as usual.

**Merge order:** `arch-api` first, then regenerate `schema.d.ts` in `arch-web`.

## Why
The documents already contain this design: `docs/specs/003_editing-history.md` lists the same endpoints, problems and `change_log` columns, `002_model.md` the validation, slug, same-environment, cascade and secret rules, and [ADR-0014] the two-role split that the issue's Decisions 2 and 3 repeat; the admin-only team/environment endpoints are the Interfaces of `008_admin.md`. The merged code from jobs 002 and 003 (`docs/history/002-.../build.md`, `003-.../build.md`) gives every hook: six model tables with `version` and non-cascading FKs, `internal/model` service and sqlc queries, `register()` with `minRole` and the default-deny test, `newProblem` mapping with `value` cleared, `Principal` with teams and `actor_kind` decided by `client_id == azp`, and `LoadMigrate`/`LoadServe` config; the dev stack already creates `arch_app` and sets `MIGRATE_DATABASE_URL`. It is high risk because it writes the audit log, adds a migration with grants and a trigger, and implements permission and secret checks, all on the Factory notes' High risk and Always escalate lists.

## Questions
None.

## Research
None.

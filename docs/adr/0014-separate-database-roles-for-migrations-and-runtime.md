# ADR-0014: Separate database roles for migrations and runtime

- Status: Proposed
- Date: 2026-11-08
- Deciders: grill session with khajonpot
- Relates to: [NFR-003], [BR-042], [ADR-0004], [ADR-0005]

## Context

[ADR-0005] and [SPEC-editing-history-08] require that the API's database role has no `UPDATE`
or `DELETE` grant on `change_log`. If the API connects as the user that owns the tables (as
the dev stack did, with `arch`), revoking grants means little: an owner keeps implicit rights
and can re-grant them to itself.

## Options considered

1. **One user, revoke on `change_log`** — simplest config; the owner can undo the revoke, so the guarantee is weak.
2. **One user plus a trigger** — blocks UPDATE/DELETE/TRUNCATE, but the owner can drop the trigger.
3. **Two users: an owner for migrations, a runtime user with DML only** — the runtime user cannot change or drop tables, and gets only `SELECT, INSERT` on `change_log`; a trigger adds a second guard. Needs a second connection string.

## Decision

Option 3. `arch-api migrate` connects with `MIGRATE_DATABASE_URL` (the owner; defaults to
`DATABASE_URL`), and the server connects with `DATABASE_URL` as the runtime role `arch_app`.
Migrations grant `arch_app` the DML it needs on model tables and only `SELECT, INSERT` on
`change_log`, and a trigger rejects `UPDATE`, `DELETE` and `TRUNCATE` on `change_log` for
everyone. An integration test checks both.

## Consequences

- `arch_app` must exist before `migrate up`: the hub dev stack creates it (`dev/postgres/init`);
  the deploy slice provisions it on RDS and stores both connection strings in External Secrets ([ADR-0012]).
- New env var `MIGRATE_DATABASE_URL` in `arch-api`'s `.env.example` and in `arch-deploy` values.
- The dev stack keeps `DATABASE_URL` on the owner until the write-API slice (which adds the grants) merges, then switches it to `arch_app`.

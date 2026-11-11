# ADR-0016: Append-only change log as built

- Status: Accepted
- Date: 2026-11-09
- Deciders: khajonpot, factory job 004-write-api-for-nodes (hub issue #5)
- Relates to: [BR-042], [NFR-003], [ADR-0005], [ADR-0014]

## Context

[ADR-0005] chose an append-only `change_log` table written in the same transaction as each change,
with columns `entity_id` and entity kinds node|edge|type|team. Spec 003 later fixed the columns
differently ([SPEC-editing-history-06], [SPEC-editing-history-08]): `entity_key` instead of
`entity_id`, an `actor_name` for display, and `environment` as an entity. [ADR-0014] added a
separate runtime role and a trigger as a second guard. The write-API slice (job 004, hub issue #5)
built the table in `arch-api` migrations `00004_change_log.sql` and `00005_app_role_grants.sql`.
Source: job 004 spec and decision, 2026-11-09.

## Options considered

1. **Keep [ADR-0005] as written** — it no longer matches spec 003 or the code.
2. **Record the table as built in a new ADR** — ADRs are append-only, so [ADR-0005] is superseded.

## Decision

Option 2. This supersedes [ADR-0005]; its approach (one row per change, same transaction, written
by the service layer, never updated or deleted) stands.

- **Columns:** `id bigserial PRIMARY KEY`, `at timestamptz NOT NULL DEFAULT now()`, `actor text`,
  `actor_name text`, `actor_kind` user|service, `source` ui|api|yaml|discovery|import (`api` for a service account's write, hub issue #18), `entity`
  node|edge|type|team|environment, `entity_key text`, `action` create|update|delete, `before jsonb`,
  `after jsonb`, with `CHECK (before IS NOT NULL OR after IS NOT NULL)`. `before`/`after` hold the
  entity's API JSON; `before` is null on create, `after` null on delete.
- **`entity_key`:** node `<environment>/<id>`, edge `<uid>`, type `node/<id>` or `edge/<id>` (node and
  edge type ids may collide; hub issue #19), team `<id>`, environment `<id>`. A type row's `before` and
  `after` hold the whole type: name, attribute schema and, for an edge type, its allowed pairs.
- **Append-only trigger:** `change_log_reject()` raises an exception; it runs `BEFORE UPDATE OR
  DELETE ... FOR EACH ROW` and `BEFORE TRUNCATE ... FOR EACH STATEMENT`, so it applies to every role,
  including the owner.
- **Grants ([ADR-0014]):** the runtime role `arch_app` gets only `SELECT, INSERT` on `change_log`
  (and `USAGE, SELECT` on `change_log_id_seq`), next to DML on the model tables.
- **Indexes:** `(entity, entity_key, at DESC, id DESC)`, and for a node's edge history two partial
  expression indexes `WHERE entity = 'edge'` on `(coalesce(after, before)->>'environment',
  coalesce(after, before)->>'from', at DESC, id DESC)` and the same with `'to'`. This needs no extra
  column because an edge's environment, `from` and `to` never change.

## Consequences

- History queries for a node read its own rows by `entity_key` and its edges' rows through the
  expression indexes, newest first by `(at, id)`.
- Every later migration that adds a table grants it to `arch_app` too; none grants `UPDATE` or
  `DELETE` on `change_log`.
- Removing the trigger or widening the `change_log` grants is a new migration and is on the
  Always escalate list.

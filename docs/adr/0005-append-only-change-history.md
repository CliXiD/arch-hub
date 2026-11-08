# ADR-0005: Append-only change history

- Status: Superseded by [ADR-0016]
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-042], [NFR-003]

## Context

Every change to a node or edge must record who, when, before and after ([BR-042]), kept
indefinitely and append-only ([NFR-003]). Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **Append-only `change_log` table written in the same transaction** — simple, consistent, queryable.
2. **Temporal tables / triggers** — automatic, but hides who made the change (the app user isn't
   the DB user) and is harder to test.
3. **Full event sourcing** — the state is rebuilt from events; much more machinery than needed.

## Decision

A `change_log` table (`id`, `at`, `actor`, `actor_kind` user|service, `entity` node|edge|type|team,
`entity_id`, `action` create|update|delete, `before` JSONB, `after` JSONB, `source` ui|yaml|...),
written by the service layer in the same transaction as each change. The application never
updates or deletes its rows; the DB role used by the API has no UPDATE/DELETE grant on it.

## Consequences

- Point-in-time views can later be built by replaying the log.
- Every write path (UI, YAML import, admin) must go through the service layer that writes the log.

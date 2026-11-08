# ADR-0004: Database, data access and migrations

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-001], [BR-003], [BR-030], [NFR-005]

## Context

The model is a typed graph ([BR-001]) with admin-defined types ([BR-003]). Impact analysis needs
transitive upstream and downstream traversal ([BR-030]) over up to 2,000 nodes and 10,000 edges in
under 2 seconds ([NFR-005]). Production targets AWS RDS. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **PostgreSQL 16, nodes and edges tables, recursive CTEs** — one database, runs on RDS, ample
   speed at this size; type attributes in JSONB validated against the type's schema.
2. **Neo4j or another graph database** — native traversal, but another system to run and secure,
   not needed at this scale.

Data access: **pgx/v5 + sqlc** (type-safe Go from SQL; handles recursive CTEs cleanly) versus an
ORM (GORM, ent). Migrations: **goose** (SQL files) versus golang-migrate or Atlas.

## Decision

PostgreSQL 16; `nodes`, `edges`, `node_types`, `edge_types`, `teams` tables; impact queries as
recursive CTEs with cycle detection. pgx/v5 with sqlc; goose SQL migrations in
`arch-api/migrations/`.

## Consequences

- Existing migrations are never edited (protected path); a schema change is a new migration.
- sqlc output is generated code (protected path); change the SQL and re-generate.
- `arch-api` is the only repo that owns schema (`implies: db`).

VERDICT: PASS

## Summary
- arch-api adds two new goose migrations, 00004_change_log.sql and 00005_app_role_grants.sql. They run after 00001-00003 and no existing migration is edited.
- 00004 creates the append-only `change_log` table with CHECK constraints, an entity index, two partial edge indexes, and triggers rejecting UPDATE, DELETE and TRUNCATE. The Down undoes the Up in the right order.
- 00005 grants `arch_app` DML on the 6 model tables, SELECT and INSERT only on `change_log`, the sequence, and SELECT on goose_db_version. This matches ADR-0014, and the Down mirrors it.
- The change is additive and safe on a live system, with no rewrite, rename, drop or data change.
- sqlc output, `dbq.ChangeLog` and the queries match the schema. `FOR UPDATE` is covered by the UPDATE grant. arch-web has no schema change and there is no schema mirror.

## Findings
None.

## Notes
- 00005 requires the `arch_app` role to exist first. The dev stack creates it, and the deploy slice must provision it on RDS (documented in ADR-0014).
- No TRUNCATE grant for `arch_app` is intended; the trigger blocks it anyway.
- `change_log` writes and migrations are on the Always escalate list, so a human should review this job.

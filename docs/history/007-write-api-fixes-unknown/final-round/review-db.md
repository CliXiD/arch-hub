VERDICT: PASS

## Summary
- arch-api adds `migrations/00007_source_api.sql` (renumbered after 00006_model_vocabulary landed). It is new, runs last, and edits no existing migration.
- It widens the `source` CHECK on nodes, edges and change_log to include `api`. The change is additive, with no data change.
- The constraint names match the Postgres defaults for the inline checks in 00002 and 00004. The Down restores the old checks.
- The sqlc queries and generated `dbq` code take `source` as a parameter, and the model enums include `api`.
- arch-web has no schema change, and no mirror rule applies.

## Findings
None.

## Notes
- Re-adding the CHECK constraints scans each table under a brief ACCESS EXCLUSIVE lock. This is fine at the current size. `NOT VALID` followed by `VALIDATE` would avoid the long lock on large tables.
- The Down fails once any `api` row exists. This is documented and unavoidable because change_log is immutable.
- I did not run the migration against a database. This review is from reading the diff.

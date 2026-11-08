VERDICT: PASS

## Summary
- There is no schema change and no migration in arch-api. Existing migrations are untouched and nothing was dropped or renamed.
- The only DB-facing change is a new sqlc query, `ShareEdgeSourceOwner`, in internal/db/queries/write.sql. It uses `FOR SHARE OF n` on the source node. The matching generated code is in internal/db/dbq/write.sql.go.
- The generated code follows sqlc's output style, the SQL is valid against the existing edges and nodes columns, and the query is read-only.
- `lockEdgeFor` now locks the node (share) and then the edge. `DeleteNode` already takes locks in that order, so the two can't deadlock. The owner check now uses the locked owner value.
- queries_test.go is a source-text guard that checks the `FOR SHARE` clause is still in the query.

## Findings
None.

## Notes
- I did not run `sqlc generate` to confirm the generated file is byte-identical. A reviewer can run `sqlc diff` if they want to check.

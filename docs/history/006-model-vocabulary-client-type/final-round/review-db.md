VERDICT: PASS

## Summary
- The job adds one new goose migration, `migrations/00006_model_vocabulary.sql`. It sorts after 00005, and no existing migration is edited.
- Up inserts the four built-in node types (`client`, `load-balancer`, `container-registry`, `job`). It appends `external→application` last in `allowed` for `calls` and `depends_on`. It sets the new `attributes_schema` literals for `calls` and `stores_data_in`.
- Down restores the 00003 literals for `depends_on`, `calls` and `stores_data_in`, character for character. It then deletes the four node types, with the edge-type updates running first.
- Every change is additive or a scoped update, keyed by id. There are no table rewrites, no NOT NULL additions and no drops or renames of columns.
- Version-pinned tests are bumped from 5 to 6 and the integration tests are extended. The change touches no Go models, sqlc output or openapi.

## Findings
None.

## Notes
- Down fails on the foreign key if nodes still use a new type. The spec intends this.
- I did not run the migration or the integration tests. I compared the SQL against 00003 and the spec by reading them.

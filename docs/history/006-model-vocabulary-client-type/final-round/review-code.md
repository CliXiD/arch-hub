VERDICT: PASS

## Summary
- arch-api adds only `migrations/00006_model_vocabulary.sql`. It adds four built-in node types, the `external → application` pair (appended last) on `calls` and `depends_on`, and the wider `calls` and `stores_data_in` attribute schemas, all as the spec gives them.
- Down restores the 00003 literals first and then deletes the four types, so it removes no nodes or edges.
- No Go behaviour change, and `internal/model`, `internal/httpapi`, `dbq` and `api/openapi.yaml` are untouched.
- Tests cover the spec. The version pins are 6, "seeded vocabulary" is updated, the new "wider vocabulary" subtest covers 201, 422 and graph cases, and `TestMigrationVocabularyRollback` compares against the real version-5 snapshot.
- The later subtests ("history", "in use", cascade delete) are adjusted for the extra rows, not weakened. `startPostgres` keeps its return values.

## Findings
None.

## Notes
- Down also resets `stores_data_in.allowed` to its unchanged 00003 value. This is harmless.
- The "wider vocabulary" subtest creates no `load-balancer` node, so that type is only checked through the seeded vocabulary test. This is acceptable.

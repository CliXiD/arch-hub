VERDICT: PASS

## Summary
- Round 2 is a rebase onto main (now with job 006) plus renumbering migration 00006 to 00007. The round-1 behaviour is unchanged.
- Only 00007_source_api.sql is new in migrations/, and 00006_model_vocabulary.sql is untouched.
- The version-7 assertions in internal/db/db_test.go and the integration readiness check match the latest migration.
- Both gates pass. arch-web still has only the three regenerated `source` unions.
- High risk (change_log constraints): a human signs off.

## Findings
None.

## Notes
- The ADR-0016 hub docs note is still to be done separately.

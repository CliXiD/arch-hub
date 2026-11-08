VERDICT: PASS

## Summary
- Edge PATCH/DELETE now share-lock the source node (`ShareEdgeSourceOwner`, `FOR SHARE OF n`) before `LockEdge`. This matches the node-then-edge order in `DeleteNode`. Error precedence is unchanged.
- The URL userinfo pattern now takes `\S+` as the password. The `token` name word is a whole-word or word-end match through a small word splitter, and the other name words keep their substring match.
- The tests match the spec. They cover the query text, an integration race for PATCH and DELETE with a `pg_stat_activity` lock-wait check, the new `TestCheckSecrets` rows, and the never-echoed and accepted-name cases.
- The README Secrets paragraph is updated. `openapi.yaml` and migrations are untouched. Checks passed.
- This job changes secret patterns, which is on the Always escalate list, so a human must sign off before merge.

## Findings
None.

## Notes
- `nameWords` handles `APIToken`, `refreshToken2`, `maxTokens` and `ACCESS_TOKEN` correctly. I traced it by hand.
- The integration lock-wait poll counts any `arch_app` backend waiting on a Lock. That is adequate here, since the subtest is serial.
- The hub's [SPEC-model-10] still quotes the old regex. The spec leaves that update to the human who signs off the patterns.

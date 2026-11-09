ESCALATE

## Summary
- One arch-api PR (CliXiD/arch-api#6) fixes the three gaps job 004 left. Edge PATCH/DELETE now read the source owner under `FOR SHARE OF n` before `LockEdge`. URL passwords containing `/`, `@` or `:` are now flagged. `token` in an attribute name only counts as a whole word or the end of a word.
- Round 1: `GATE: PASS`. The code, db and security reviews are all `VERDICT: PASS` with no findings. All 9 acceptance criteria have evidence, and the integration test failed against the old code, so it really catches the race.
- I spot-checked it myself. `TestCheckSecrets` and `TestShareEdgeSourceOwnerLocksTheNode` pass. `api/openapi.yaml`, `migrations/` and `go.mod` are unchanged from `origin/main`.
- I am escalating only because the job changes the secret-detection patterns. That is on the Always escalate list, and issue Decision 1 requires a human to sign off.

## Why
The change is correct, tested, stays within scope and follows the spec. I would merge it on the engineering merits. Changes to the secret-detection patterns are on the Always escalate list, so a human has to accept the new rules. One of them also lets through more names than the spec's examples show.

## Acceptance criteria
1. [arch-api] `ShareEdgeSourceOwner` with `FOR SHARE OF n` in `write.sql` and in the generated `dbq`: met. It is in the diff, and the builder ran `make sqlc` with no drift.
2. [arch-api] `lockEdgeFor` calls the share query before `LockEdge` and no longer calls `NodeOwnerKind`: met (I read the diff in `internal/model/write.go`).
3. [arch-api] A unit test checks for `FOR SHARE OF n` in the query: met. I ran `TestShareEdgeSourceOwnerLocksTheNode` and it passes.
4. [arch-api] An integration subtest shows PATCH and DELETE wait on the lock, then get 403 with no change_log row: met. build.md shows it passing, and the negative control fails against the old code. The gate does not run integration tests.
5. [arch-api] URL values `postgres://u:p/w@h` and `https://u:p@ss@h` are rejected, naming only the path. `ssh://git@...` and `https://host:8443/path` are accepted: met. I ran `TestCheckSecrets` and it passes.
6. [arch-api] Names `tokens_per_minute` and `max_tokens` are accepted. `token`, `api_token`, `access_token`, `password` and `client_secret` are rejected. Old rows keep their results: met (the same test run).
7. [arch-api] `TestSecretsAreNeverEchoed` has the new URL rows and the `access_token` row: met. It passes in the gate's `./internal/httpapi` run.
8. [arch-api] `openapi.yaml` and migrations are unchanged: met. I checked with `git diff --exit-code`.
9. [arch-api] The README Secrets paragraph describes the new rules: met (the README diff).

## Merge order
1. CliXiD/arch-api#6 (the only PR, with no callers to sequence).

## Docs impact
- `docs/specs/002_model.md` [SPEC-model-10]: replace the quoted name regex with the new rule. The name matches `(?i)(password|passwd|secret|api[_-]?key|private[_-]?key|credential)` anywhere, or has a word (split on non-letters and camelCase) that equals `token` or ends in `token`. Also state that a URL with `user:pass@` userinfo is flagged whatever the password holds. The human who signs off the patterns makes this edit in the hub after merge.
- `docs/specs/001_identity-access.md` [SPEC-identity-access-05]: no text change.
- No new ADR.

## For the human
Changes to the secret-detection patterns are on the Always escalate list, and issue Decision 1 says a human signs off the new patterns. Everything else passed: the checks, three reviews with no findings, and every acceptance criterion. Please decide whether to accept these rules, then merge CliXiD/arch-api#6 yourself.

1. **URL password pattern** (`internal/model/secrets.go`): the password part becomes `\S+`.
   - `postgres://u:p/w@h` and `https://u:p@ss@h` are now rejected.
   - Known false positive: a value like `https://example.test:8443/a@b`, with `host:port` and an `@` later in the URL, is now rejected too. The spec accepted this under NFR-002 ("err towards rejecting").
2. **`token` name rule**: a word (split on non-letters and camelCase) that equals `token` or ends in `token` is a secret.
   - Still rejected: `token`, `access_token`, `apiToken`, `accesstoken`, `token_value`, `tokenId`.
   - Now accepted: `tokens_per_minute`, `max_tokens`, `tokenizer`.
   - The security review found more names that now pass: `tokenvalue`, `tokenid`, `bearertokenvalue` and `authtokens`, because they have no word boundary. If that is not acceptable, say so and the rule needs another round.
3. **The other name words** (`password`, `secret`, `api_key`, ...) keep the substring match. No change.

After merge, update the SPEC-model-10 line in `docs/specs/002_model.md` to the rule you accept (see Docs impact).

Files to look at: `internal/model/secrets.go`, `internal/model/secrets_test.go` and the README Secrets paragraph in PR #6. Also see the Notes in `factory/jobs/005-write-api-hardening-follow/round-1/review-security.md`.

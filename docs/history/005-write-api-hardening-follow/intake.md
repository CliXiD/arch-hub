DECISION: ACCEPT
RISK: high
SURFACES: security
REPOS: arch-api
RESCOPED: no

## Summary
- Accepted as written: three contained fixes in `arch-api`, no API shape change, no other repo.
- All three gaps are confirmed in the code: `lockEdgeFor` reads the source owner with an unlocked `NodeOwnerKind`; the URL pattern excludes `/` and `@` from the password; `token` matches as a substring.
- High risk by the Factory notes (secret detection, permission check); the new secret patterns go to a human for sign-off, as Decision 1 says.
- SPEC-model-10 quotes the current name regex word for word; its text must change to the new rule when the patterns are signed off. I read Decision 1 as covering that; say so if not.

## Scope
One PR in `arch-api`; no change to `openapi.yaml`, `arch-web` or `arch-deploy`.

1. **Edge PATCH/DELETE owner read under lock.** Add a sqlc query that reads the source node's owner and kind `FOR SHARE OF n` (sibling of `LockNode`, which uses `FOR UPDATE OF n`), and use it in `lockEdgeFor` so the permission check sees the owner as it stands in the write transaction. Lock the node before the edge (read the edge's `from` first, take the node share lock, then `LockEdge FOR UPDATE`; `from` cannot change, so the re-read is safe). That keeps the same lock order as `DeleteNode` (node, then its edges) and avoids a deadlock between an edge write and a node delete. A test shows the query text uses `FOR SHARE`; an integration test (behind the existing `integration` tag) shows an edge PATCH by an editor of the old team waits for an uncommitted owner change and then gets `403`.
2. **URL credentials whatever the password holds.** Widen the userinfo pattern so the password part may contain `/` and `@`: `postgres://u:p/w@h` and `https://u:p@ss@h` give `422 /problems/secret-detected` naming `body.attributes.<name>` only. A plain `scheme://host:port/path` without `@` stays accepted; `ssh://git@host/repo` (user only) stays accepted. A URL with `host:port` and an `@` later in the path or query will now be flagged too; that is the price of the rule and acceptable under [NFR-002] (err towards rejecting), so note it in the tests.
3. **Secret names as whole words.** Match the secret words after splitting the attribute name on `_`, `-` and camelCase, so `tokens_per_minute` and `max_tokens` are accepted while `token`, `api_token`, `access_token`, `apiToken`, `password`, `db_passwd`, `client_secret`, `API_KEY`, `api-key`, `privateKey`, `private_key` and `Credentials` are still rejected (every case in the current `secrets_test.go` keeps its result). Table-driven tests for each case; the error still names the path only.

Also update the Secrets paragraph of `arch-api/README.md` to the new name rule. The hub's SPEC-model-10 quotes the current regex; the human who signs off the patterns updates that line to the final rule (hub document, outside the repo PR).

Left out: any other secret pattern (per the issue), `arch-web` screens, and the same locked read in `POST /edges` (it reads the owner with the same unlocked query; the builder may reuse the new query there if it is a one-line change, but it is not required here).

## Why
`repos/arch-api/internal/model/write.go` `lockEdgeFor` locks the edge `FOR UPDATE` and then calls `NodeOwnerKind`, which `internal/db/queries/write.sql` defines as a plain `SELECT`; `secrets.go` uses `[^\s/@]+@` for the password and matches `token` anywhere in the name, so the three gaps from the job 004 security review are exactly as described. The fix is contained (one query, two regexes or a small name tokenizer, tests) and the acceptance criteria are precise, so one small PR fits. The only tension is that `docs/specs/002_model.md` SPEC-model-10 spells out the current regex; the issue's Decision 1 explicitly makes this job change the patterns under human sign-off, so I accept and flag the document update rather than ask.

## Research
None.

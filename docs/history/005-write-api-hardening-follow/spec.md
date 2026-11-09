# Write API hardening: locked edge owner read, URL passwords, token names

> Issue #14: Write API hardening follow-ups from job 004

## Summary
- Fixes the three non-blocking gaps the job 004 security review left in the `arch-api` write path; nothing else changes and no other repo is involved.
- Edge PATCH/DELETE will read the source node's owner under `FOR SHARE` inside the write transaction. The node is locked before the edge, so a concurrent owner change can't race the permission check ([SPEC-identity-access-05]).
- The URL-credential value pattern will flag passwords that contain `/` or `@` ([SPEC-model-10], [NFR-002]).
- `token` in an attribute name will only count as a secret when it is a whole word, or the end of a word, so `tokens_per_minute` and `max_tokens` are accepted. Every other name word keeps today's substring match.
- No API shape change: `api/openapi.yaml` stays byte-identical (Decision 2). A human must sign off the new patterns (Decision 1, Always escalate).

## Context
- `arch-api:internal/model/write.go`
  - `UpdateEdge` (around line 380) and `DeleteEdge` (around line 427) both call `lockEdgeFor`.
  - `lockEdgeFor` (around line 440) works in this order:
    1. Parses the uid.
    2. Runs `q.LockEdge` (`SELECT ... FROM edges WHERE uid = $1 FOR UPDATE`).
    3. Calls `q.NodeOwnerKind`, a plain unlocked `SELECT n.owner, t.kind ... WHERE n.environment = $1 AND n.id = $2`.
    4. Checks `a.can(from.Owner)`, then the version.
  - It returns errors in this order: `ErrNotFound`, `ForbiddenError`, `ErrStale`.
  - `DeleteNode` (around line 248) takes its locks in a fixed order: the node first (`lockNode`, which uses `LockNode` with `FOR UPDATE OF n`), then its edges (`LockNodeEdges ... FOR UPDATE`).
  - `UpdateNode` changes `owner` under the same node `FOR UPDATE` lock. A `FOR SHARE` on the node row therefore waits for an uncommitted owner change and then sees the committed owner.
  - `CreateEdge` (around line 290) uses the helper `nodeOwnerKind` with the same unlocked query. It is left as is (see Out of scope).
- `arch-api:internal/db/queries/write.sql` holds the write queries for sqlc.
  - `arch-api:internal/db/dbq/` is sqlc output, regenerated with `make sqlc` (`go tool sqlc generate`) and never edited by hand.
  - `edges.from_id` has a foreign key to `nodes (environment, id)` (`arch-api:migrations/00002_model.sql`), so an edge's source node always exists. `from` can't change after an edge is created.
- `arch-api:internal/model/secrets.go` has the secret patterns.
  - `secretName = (?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)` is matched as a substring of the whole name.
  - The URL value pattern is `[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]*:[^\s/@]+@`. Its password part excludes `/` and `@`.
  - `CheckSecrets` returns a `*SecretError` with locations `body.attributes.<name>` (or `[i]` for array elements) and never holds a value.
- Existing tests to extend:
  - `arch-api:internal/model/secrets_test.go`: `TestCheckSecrets`, table-driven, asserts locations and that the error never contains the value.
  - `arch-api:internal/httpapi/routes_write_test.go`: `TestSecretsAreNeverEchoed` (around line 487), which runs every row through node and edge POST and PATCH and asserts `422`, the single location, and that no 6-character slice of the value appears in the body or the logs.
  - `arch-api:cmd/arch-api/write_integration_test.go`: `TestWriteIntegration`, behind `//go:build integration`, against a real PostgreSQL. It uses `owner` (the migration-owner pool), `app`, and the `editor` writer with teams `[platform]`. Team `core` and nodes owned by `platform` and `core` are created in earlier subtests. It has helpers `writer.expect` and `problemBody`.
  - `arch-api:internal/db/db_test.go` (package `db_test`).
- `arch-api:README.md` around lines 157-160: the "Secrets." paragraph lists the name words, including `token`.
- Hub: [SPEC-model-10] in `docs/specs/002_model.md` quotes today's name regex word for word.

## Contract
Single repo; no contract.

## Requirements

### arch-api

1. **New query `ShareEdgeSourceOwner`.** Add it to `internal/db/queries/write.sql`, next to `LockEdge`:
   ```sql
   -- name: ShareEdgeSourceOwner :one
   SELECT n.owner
   FROM edges e
   JOIN nodes n ON n.environment = e.environment AND n.id = e.from_id
   WHERE e.uid = $1
   FOR SHARE OF n;
   ```
   Then regenerate `internal/db/dbq/` with `make sqlc`; don't hand-edit it. It locks only the source node row, in share mode.
2. **`lockEdgeFor` new order.**
   1. Parse the uid. Parse failure gives `ErrNotFound`.
   2. Call `q.ShareEdgeSourceOwner`. `pgx.ErrNoRows` gives `ErrNotFound`.
   3. Call `q.LockEdge` (unchanged, `FOR UPDATE`). `pgx.ErrNoRows` gives `ErrNotFound`.
   4. Call `a.can(owner)` with the owner from step 2.
   5. Check the version: a mismatch gives `ErrStale`.

   `lockEdgeFor` no longer calls `NodeOwnerKind`. The error precedence (not found, forbidden, stale) and every response stay as they are. Update the doc comment to say it share-locks the source node, then locks the edge (the same node-then-edge order as `DeleteNode`, so they can't deadlock).
3. **A unit test for the lock clause.** Add it to `internal/db/db_test.go` or a new `internal/db/queries_test.go`. It reads `internal/db/queries/write.sql`, finds the `-- name: ShareEdgeSourceOwner` block, and asserts that block contains `FOR SHARE OF n`.
4. **An integration subtest in `TestWriteIntegration`** (integration tag; place it before "deleting a node deletes its edges").
   1. Pick an edge whose source node is owned by `platform`. Read its version.
   2. On the `owner` pool, begin a transaction and run `UPDATE nodes SET owner = 'core' WHERE environment = ... AND id = ...` without committing.
   3. In a goroutine, have `editor` (teams `[platform]`) send `PATCH /api/v1/edges/{uid}` with the current `If-Match`.
   4. Poll `pg_stat_activity` on the `owner` pool until a backend has `wait_event_type = 'Lock'` (with a timeout of a few seconds). This proves the PATCH waits instead of reading the old owner.
   5. Commit. Assert that the PATCH returns `403` with `type /problems/forbidden`, and that no `change_log` row was written for the edge.
   6. Restore the owner afterwards, or use a node created only for this subtest, so later subtests are unaffected.

   Do the same for `DELETE` (one PATCH and one DELETE case, or a two-row table).
5. **URL credentials whatever the password holds.** In `secrets.go`, replace the URL-with-userinfo pattern with:
   ```
   [A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]*:\S+@
   ```
   - The user part is unchanged, so `ssh://git@host/repo` (user only) stays accepted.
   - The password part may now hold `/`, `@` and `:`.
   - The PEM and AWS patterns are unchanged.
6. **`token` as a whole word.**
   - Remove `token` from the `secretName` regex. The rest stays exactly `(?i)(password|passwd|secret|api[_-]?key|private[_-]?key|credential)`, matched as a substring as today.
   - Add a small unexported word splitter. Words are maximal runs of ASCII letters. Any non-letter (`_`, `-`, `.`, digits, ...) separates words. A camelCase boundary (lower to upper) splits, and so does an acronym boundary (`APIToken` gives `API`, `Token`).
   - A name is a secret when the `secretName` regex matches, or when any word, lowercased, equals `token` or ends with `token` (`accesstoken`, `apitoken`).
   - Words such as `tokens` or `tokenizer` don't match.
7. **Extend `TestCheckSecrets`.** Every existing row keeps its result. Add these rows:
   - **Values rejected:** `postgres://u:p/w@h`, `https://u:p@ss@h`, `mysql://u:a:b@h`.
   - **Value accepted:** `https://example.test:8443/path`.
   - **Value now rejected, documenting the accepted false positive:** `https://example.test:8443/a@b`. Add a comment that [NFR-002] errs towards rejecting.
   - **Names accepted:** `tokens_per_minute`, `max_tokens`, `maxTokens`, `tokenizer`.
   - **Names rejected:** `token`, `api_token`, `access_token`, `apiToken`, `APIToken`, `ACCESS_TOKEN`, `accesstoken`, `refreshToken2`, `password`, `client_secret`.
   - Each rejected row asserts only its `body.attributes.<name>` location, and the existing "never holds the value" assertion.
8. **Extend `TestSecretsAreNeverEchoed`.** Add rows for `postgres://u:p/w@h` and `https://u:p@ss@h` (attribute `dsn`, location `body.attributes.dsn`) and a row for the name `access_token`.
   - Choose values whose 6-character slices can't occur in a normal problem body. If a slice could collide (for example `https:`), use a longer, distinctive value with the same shape, such as `https://usr:p@ssw0rd-Qx7@db.example.test`.
   - Add a row to the existing table-driven handler test (or a new small test) showing `tokens_per_minute` is accepted on `POST /api/v1/nodes` (the fake writer returns its usual success).
9. **README.** Update the "Secrets." paragraph in `README.md`:
   - The name words match anywhere in the name, except `token`, which counts only as a whole word or the end of one (`access_token`, `apiToken`; not `max_tokens`).
   - A URL with a password is flagged whatever characters the password holds.
10. **No change to `api/openapi.yaml`.** It stays unchanged and `make openapi-check` passes. No new migration, no Huma type change, no new log line.

## Acceptance criteria
1. [arch-api] `internal/db/queries/write.sql` contains a `ShareEdgeSourceOwner` query ending in `FOR SHARE OF n`, and `internal/db/dbq/write.sql.go` contains the generated `ShareEdgeSourceOwner` method. Verify with `grep -n "FOR SHARE OF n" internal/db/queries/write.sql internal/db/dbq/write.sql.go`, and `go tool sqlc diff` (or `make sqlc && git diff --exit-code internal/db/dbq`) shows no drift.
2. [arch-api] `lockEdgeFor` in `internal/model/write.go` calls `ShareEdgeSourceOwner` before `LockEdge` and no longer calls `NodeOwnerKind`. Verify with `grep -n "ShareEdgeSourceOwner\|LockEdge\|NodeOwnerKind" internal/model/write.go`: inside `lockEdgeFor`, the share call comes first and `NodeOwnerKind` does not appear.
3. [arch-api] The new unit test asserting `FOR SHARE OF n` in the `ShareEdgeSourceOwner` block passes: `go test -count=1 -run 'Share|Quer' ./internal/db/...`.
4. [arch-api] `go test -tags integration -count=1 -run TestWriteIntegration ./cmd/arch-api/` passes with podman or docker available. The new subtest shows an editor's edge PATCH and DELETE wait on an uncommitted owner change to `core` (a backend in `pg_stat_activity` with `wait_event_type = 'Lock'`), then return `403 /problems/forbidden` once it commits, with no `change_log` row for the edge.
5. [arch-api] `go test -count=1 -run TestCheckSecrets ./internal/model/` passes, with rows proving the following:
   - `postgres://u:p/w@h` and `https://u:p@ss@h` give a `SecretError` naming only `body.attributes.<name>`.
   - `ssh://git@example.test/repo` and `https://example.test:8443/path` give none.
6. [arch-api] The same test run proves these names:
   - Accepted: `tokens_per_minute` and `max_tokens`.
   - Rejected: `token`, `api_token`, `access_token`, `password` and `client_secret`, each with only its own location.
   - Every pre-existing row keeps its result.
7. [arch-api] `go test -count=1 -run TestSecretsAreNeverEchoed ./internal/httpapi/` passes with the new URL rows on node and edge POST and PATCH. Each request returns `422`, `type /problems/secret-detected`, and `errors` equal to `[{"location":"body.attributes.dsn","message":"looks like a secret"}]`, and no 6-character slice of the value appears in the response body or the captured logs.
8. [arch-api] `api/openapi.yaml` is unchanged against the base: `git diff --exit-code origin/main -- api/openapi.yaml migrations/`.
9. [arch-api] The "Secrets." paragraph in `README.md` describes the whole-word `token` rule and URL passwords with any characters: `grep -n "max_tokens" README.md`.

## Merge and deploy order
Only `arch-api`, as one PR. `merge_order` has nothing else to sequence: there is no API, schema or config change, so no caller needs to move. Because this job changes the secret-detection patterns, it is on the Always escalate list. A human signs off the patterns before merge (Decision 1), even though `arch-api` normally auto-merges.

## Out of scope
- Any other change to the secret patterns: the other name words keep their substring match, and the PEM and AWS value patterns stay as they are (issue Out of scope).
- Changing `CreateEdge` (`POST /edges`) to read the source owner under a lock. It still uses the unlocked `NodeOwnerKind`. The new query is keyed by edge uid and doesn't fit that path, so it is left for a later job.
- Locking in `UpdateNode`, `DeleteNode` or team and environment writes.
- Any change to `api/openapi.yaml`, Huma types, error shapes or status codes.
- Migrations (and `migrations/*` is protected anyway).
- `arch-web` screens and `arch-deploy`.
- New configuration or options to turn the patterns on or off.
- Editing [SPEC-model-10] in the hub as part of the repo PR (see Docs impact).

## Assumptions
- **The whole-word rule applies to `token` only.** Every other name word (`password`, `passwd`, `secret`, `api key`, `private key`, `credential`) keeps today's substring match. The issue forbids any other pattern change and names only `token` as a false positive. Splitting every word would newly accept names like `dbpassword` or `secretkey`, which would weaken [NFR-002]. This narrows intake's "split on `_`, `-` and camelCase" to the one word that needs it.
- **A word that ends in `token` (`accesstoken`, `apitoken`) is still a secret.** Such a name denotes a token. Only longer words like `tokens` or `tokenizer` are let through, which errs towards rejecting.
- **The URL password part becomes `\S+`.** The issue says "whatever characters the password holds". As a result, `https://host:8443/a@b` (host:port followed by an `@` later in the URL) is now flagged. Intake accepted that false positive under [NFR-002], and the tests document it.
- **One join query (`ShareEdgeSourceOwner`, by edge uid) instead of a separate `FOR SHARE` node query plus an unlocked edge read.** It is one query and one round trip. It takes the node share lock before the edge's `FOR UPDATE`, which keeps intake's node-then-edge lock order. The owner it reads is current, because PostgreSQL re-checks a locked row after waiting.
- **The query text is checked with a unit test on `queries/write.sql`.** The generated SQL constants in `dbq` are unexported and the folder is generated, so a test can't use them there. The integration test proves the behaviour.
- **The human who signs off the patterns also updates the SPEC-model-10 line in the hub.** Intake reads Decision 1 as covering that update.

## Docs impact
- `docs/specs/002_model.md` [SPEC-model-10]: replace the quoted name regex with the new rule. The rule: `(?i)(password|passwd|secret|api[_-]?key|private[_-]?key|credential)` anywhere in the name, or a word (split on non-letters and camelCase) equal to or ending in `token`. Also state that a URL with userinfo `user:pass@` is flagged whatever the password holds. This is done by the human who signs off the patterns, in the hub, after merge.
- `docs/specs/001_identity-access.md` [SPEC-identity-access-05]: no text change. The behaviour now matches it exactly under concurrency.
- No new ADR.

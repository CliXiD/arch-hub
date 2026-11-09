STATUS: READY

# Build: Write API hardening: locked edge owner read, URL passwords, token names

## Summary
- Edge PATCH/DELETE now share-lock the source node and read its owner (`ShareEdgeSourceOwner`, `FOR SHARE OF n`) before locking the edge, so the permission check waits for an uncommitted owner change instead of reading the old owner.
- The URL-with-userinfo value pattern's password part is now `\S+`: passwords holding `/`, `@` or `:` are flagged.
- `token` in an attribute name counts only as a whole word or a word's end (ASCII-letter runs, split at camelCase and acronym boundaries); the other name words keep their substring match.
- README "Secrets." paragraph updated; `api/openapi.yaml` and migrations untouched.
- Draft PR: https://github.com/CliXiD/arch-api/pull/6 (needs human sign-off: secret patterns are on the Always escalate list).

## Changes
### arch-api
- `internal/db/queries/write.sql`: new `ShareEdgeSourceOwner :one` query (edge joined to its source node, `FOR SHARE OF n`), next to `LockEdge`.
- `internal/db/dbq/write.sql.go`: regenerated with `make sqlc` (adds `ShareEdgeSourceOwner`).
- `internal/model/write.go`: `lockEdgeFor` now parses the uid, calls `ShareEdgeSourceOwner` (no rows gives `ErrNotFound`), then `LockEdge`, then `a.can(owner)`, then the version check. It no longer calls `NodeOwnerKind`. Doc comment explains the node-then-edge order. `CreateEdge` is unchanged (out of scope).
- `internal/db/queries_test.go` (new): `TestShareEdgeSourceOwnerLocksTheNode` reads `queries/write.sql` and asserts the `ShareEdgeSourceOwner` block contains `FOR SHARE OF n`.
- `cmd/arch-api/write_integration_test.go`: new subtest "an edge write waits for its source node's owner change" (patch and delete rows), placed after "in use" and before "deleting a node deletes its edges". It uses dedicated nodes `race-patch` and `race-delete`, so the later counts are unaffected.
- `internal/model/secrets.go`: `token` removed from `secretName`; the URL pattern becomes `[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]*:\S+@`; new unexported `secretNameToken` and `nameWords` (plus `isLetter`/`isUpper`).
- `internal/model/secrets_test.go`: added the rows the spec lists, including the documented false positive `https://example.test:8443/a@b` with a comment citing [NFR-002].
- `internal/httpapi/routes_write_test.go`: `TestSecretsAreNeverEchoed` gains `postgres://u:p/w@h` and `https://usr:p@ssw0rd-Qx7@db.example.test` (attribute `dsn`) and an `access_token` row. New `TestTokenWordsAreAccepted` shows `tokens_per_minute` gets 201 on `POST /api/v1/nodes`.
- `README.md`: the "Secrets." paragraph describes the whole-word `token` rule and URL passwords with any characters.

## Acceptance criteria
1. [x] [arch-api] ShareEdgeSourceOwner query and generated method: `grep -n "FOR SHARE OF n"` matches `internal/db/queries/write.sql:55` and `internal/db/dbq/write.sql.go:413`. After the commit, `make sqlc && git diff --exit-code internal/db/dbq` shows no drift.
2. [x] [arch-api] Inside `lockEdgeFor`, `ShareEdgeSourceOwner` comes first (line 6 of the function) and `LockEdge` second (line 13). `NodeOwnerKind` doesn't appear in the function; only the `CreateEdge` helper `nodeOwnerKind` still uses it.
3. [x] [arch-api] `go test -count=1 -run 'Share|Quer' ./internal/db/...` passes (`TestShareEdgeSourceOwnerLocksTheNode`).
4. [x] [arch-api] `go test -tags integration -count=1 -run TestWriteIntegration ./cmd/arch-api/` passes (podman, `DOCKER_HOST` at the podman socket, `TESTCONTAINERS_RYUK_DISABLED=true`).
   - Both the patch and delete rows see an `arch_app` backend with `wait_event_type = 'Lock'`, then get `403 /problems/forbidden` (detail names `core`) after the commit, with no `change_log` row for the edge.
   - Negative control: I put the old `lockEdgeFor` back temporarily and both rows failed ("the edge write waits on the node lock" timed out), then I restored the new code.
5. [x] [arch-api] `TestCheckSecrets` passes.
   - `postgres://u:p/w@h`, `https://u:p@ss@h` and `mysql://u:a:b@h` give only `body.attributes.dsn`.
   - `ssh://git@example.test/repo` and `https://example.test:8443/path` give none.
6. [x] [arch-api] The same run proves the names.
   - Accepted: `tokens_per_minute`, `max_tokens`, `maxTokens`, `tokenizer`.
   - Rejected, each with only its own location: `token`, `api_token`, `access_token`, `apiToken`, `APIToken`, `ACCESS_TOKEN`, `accesstoken`, `refreshToken2`, `password`, `client_secret`.
   - Every pre-existing row is unchanged and passes.
7. [x] [arch-api] `go test -count=1 -run TestSecretsAreNeverEchoed ./internal/httpapi/` passes. The new URL rows on node and edge POST and PATCH return 422 `/problems/secret-detected` with the single `body.attributes.dsn` error, and no 6-character slice of the value appears in the body or the logs. The `access_token` row passes the same way.
8. [x] [arch-api] `git diff --exit-code origin/main -- api/openapi.yaml migrations/` exits 0, and `make openapi-check` passes.
9. [x] [arch-api] `grep -n "max_tokens" README.md` matches line 159, in the Secrets paragraph.

## Validation
### arch-api
- `FACTORY_HUB=... FACTORY_REPO_KEY=arch-api FACTORY_BASE=origin/main bash factory/checks/arch-api.sh`: passed (vet, golangci-lint 0 issues, unit tests, build, openapi-check).
- `go vet -tags integration ./cmd/arch-api/` and `go tool golangci-lint run --build-tags integration ./cmd/arch-api/`: passed (0 issues).
- `go test -tags integration -count=1 -run TestWriteIntegration ./cmd/arch-api/`: passed.
- `make sqlc` after the commit: no diff.

## Log
### Round 1
- Implemented requirements 1 to 10 in three commits: the locking fix with its tests, the secret patterns with their tests, and the README.
- Checked that the integration subtest discriminates: it fails against the old unlocked owner read.
- Pushed `factory/005-write-api-hardening-follow` and opened draft PR CliXiD/arch-api#6 against `main`. It's a single-repo job, so there are no related PRs.
- Not done here, per the spec: the [SPEC-model-10] update in the hub is left to the human who signs off the patterns.

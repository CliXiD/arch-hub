ESCALATE

## Summary
- Round 2 rebased both branches onto `origin/main` as feedback 1 asked. Both now contain `origin/main` (arch-api `f2622ac`, arch-web `0031c52`), so the conflict that blocked the last decision is gone.
- arch-api: a token is a service account only when `client_id` == `azp`. The JWKS cache fetches outside its lock through singleflight, with a 5 s failure backoff and the 30 s unknown-`kid` limit. The API returns `503 /problems/auth-unavailable` (`Retry-After: 5`) while keys have never loaded. A 1 MB body limit returns `413 /problems/too-large`. The servers have 10/30/30/120 s timeouts.
- arch-web: after a `401` the app signs in again automatically at most once per 60 s (`sessionStorage` `arch.reauth.at` holds a timestamp only). A second `401` in that window shows a "session rejected" state. A `503 auth-unavailable` shows the existing "Sign-in is unavailable" state.
- Round 2 gate is PASS and all six reviews are PASS. I re-ran the auth tests under `-race` and the httpapi tests myself, and regenerated `schema.d.ts` from the job's `openapi.yaml`. The output is byte-identical to the committed file.
- It still escalates, because it changes token validation and the auth middleware (`accessMiddleware`, `principal.go`, `jwks.go`, `verifier.go`). The Factory notes list that under Always escalate.

## Why
The build meets the spec, stays within intake's Scope and REPOS, follows the Contract, and is now rebased on main. But it changes auth middleware and the rule that decides whether a caller is a service or a user. That rule is what the next job (#5) writes into `change_log` as `actor_kind`. The Factory notes require a human for this whatever the reviews say. The job also makes `golang.org/x/sync` a direct dependency. It was already in the module graph as indirect.

## Acceptance criteria
1. [arch-api] Principal mapping table test: met. I ran `TestPrincipalFromClaims` and it passes. It covers `client_id == azp` (service), the `service-account-` username without `client_id` (user), and `client_id != azp` (user). `grep service-account- principal.go` finds nothing.
2. [arch-api] Known `kid` not blocked by an in-flight refetch, and 20 concurrent unknown-`kid` requests make one fetch: met. I ran `TestVerifierKnownKidDuringRefetch` and `TestVerifierConcurrentUnknownKidSharesOneFetch` under `-race` and both pass. The diff shows `mu` is never held during `fetch`.
3. [arch-api] Fake-clock tests (29 s/30 s refetch, 4 s/5 s failure backoff on first load and after load, down then up): met. `TestVerifierUnknownKid`, `TestVerifierFailureBackoff` and `TestVerifierJWKSDownIsUnavailable` pass in my `-race` run.
4. [arch-api] `503` with `Retry-After: 5` while JWKS is down from start-up, `200` once it is up and 5 s have passed, `401` without a token: met. I ran `TestAuthUnavailable` and it passes.
5. [arch-api] Body-limit table (exactly 1 MB, 1 MB+1 with `Content-Length`, 1 MB+1 chunked) and the server timeouts: met. I ran `TestBodyLimit` and `TestNewServerTimeouts` and both pass.
6. [arch-api] `openapi.yaml` lists `413`/`503` under `/api/v1/me` and `make openapi-check` passes: met. Round 2 checks.md runs `make openapi-check` and exits 0. The diff adds the responses to every `/api/v1` operation.
7. [arch-api] Manual local-stack check: met per build.md for round 1. The service token got `actor_kind: "service"`, the editor got `"user"`, and an unreachable JWKS gave `503` + `Retry-After: 5`. For the outage it used an unreachable `OIDC_JWKS_URL` instead of stopping Keycloak. Round 2 did not repeat the check after the rebase, but the rebase did not change the auth code paths.
8. [arch-api] README covers the problems, the timeouts and the `client_id == azp` rule: met (per build.md, and it is in the diff).
9. [arch-web] Capped re-sign-in, the rejected state with both buttons, and no tokens in `sessionStorage`: met. 30 tests pass in round 2 checks. The `AuthProvider` diff writes only `String(Date.now())` under `arch.reauth.at`.
10. [arch-web] `503 auth-unavailable` shows "Sign-in is unavailable, try again", and "Try again" refetches: met. The `Shell.tsx` diff adds this, and it is tested per build.md.
11. [arch-web] `schema.d.ts` matches `gen:api` output from the job's `openapi.yaml`, and typecheck passes: met. This is my cross-repo check: running `openapi-typescript ../arch-api/api/openapi.yaml` gives a file identical to the committed one. Typecheck passes in checks.md.
12. [arch-web] README "Session" section: met (it is in the diff).

## Merge order
1. CliXiD/arch-api#4: merge and deploy first. It defines the new problem types and `openapi.yaml`. Deploying it alone is safe, because the current web app shows a generic error on `503`.
2. CliXiD/arch-web#4: merge and deploy second. Its `schema.d.ts` was generated from arch-api#4's `openapi.yaml`.
No arch-deploy change.

## Docs impact
- `docs/specs/001_identity-access.md`, *Interfaces*: add `503 /problems/auth-unavailable` (`Retry-After: 5`) and `413 /problems/too-large` to "Errors on every endpoint".
- `docs/specs/001_identity-access.md`, [SPEC-identity-access-09]: a `401` from the API triggers at most one automatic sign-in per 60 s. After that the web app shows "Your session was rejected by the API. Try signing in again." with "Sign in again" and "Sign out".
- `docs/specs/009_operations.md`, *Non-functional*: the API server's read and write timeouts are 30 s and the idle timeout is 120 s (read-header stays 10 s; the metrics server gets the same timeouts). Add the 1 MB default body limit with `413 /problems/too-large`, overridden per route only where a spec says so ([SPEC-yaml-as-code-03]).

## For the human
The rebase you asked for is done, both PRs are mergeable, and gate and reviews pass. This escalates only because it changes token validation and the auth middleware, which is on the Always escalate list. Please review and merge CliXiD/arch-api#4 first, then CliXiD/arch-web#4. Check these points:

1. **Service-account rule** (`arch-api:internal/auth/principal.go`): `actor_kind` is `service` only when `client_id` is set and equals `azp`. This is the value #5 will write to `change_log`. Confirm that every production CI client will get the `client_id` mapper (user session note `clientId`), and that no human-facing client will. Without the mapper, CI tokens count as users.
2. **JWKS cache** (`arch-api:internal/auth/jwks.go`): the lock scope, the singleflight on `context.WithoutCancel`, and `mayFetch`. After a failed fetch, only the 5 s backoff applies, not the 30 s refetch interval. So while Keycloak is down after keys have loaded, tokens with random `kid`s can trigger one fetch every 5 s.
3. **503 vs 401** (`arch-api:internal/httpapi/api.go`, `accessMiddleware`): while keys have never loaded, any parseable JWT gets `503`, which tells an unauthenticated caller that Keycloak is unreachable. The spec accepts this.
4. **Body limit** (`arch-api:internal/httpapi/bodylimit.go`): it runs before authentication and buffers chunked bodies up to 1 MB per request in memory. `ReadTimeout` 30 s bounds slow senders.
5. **Dependency**: `golang.org/x/sync` moves from indirect to direct in `go.mod`. The version is unchanged.

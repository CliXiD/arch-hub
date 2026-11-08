STATUS: READY

# Build: Harden auth and HTTP server after the walking skeleton

## Summary
- arch-api: a token is a service account only when `client_id` == `azp`. The JWKS cache no longer holds its lock during network calls, shares one fetch between concurrent callers (singleflight on `context.WithoutCancel`) and backs off 5 s after a failure. The 30 s unknown-`kid` limit stays.
- arch-api: a bearer token gets `503 /problems/auth-unavailable` with `Retry-After: 5` while the keys have never been loaded. Every route has a 1 MB body limit (`413 /problems/too-large`, checked before auth). Both servers have 10/30/30/120 s timeouts. OpenAPI is regenerated.
- arch-web: a `401` triggers at most one automatic sign-in per 60 s (`sessionStorage` `arch.reauth.at`, timestamp only). A second one shows the "session rejected" state. A `503 auth-unavailable` shows "Sign-in is unavailable, try again".
- Round 1: everything in the spec is implemented. PRs: CliXiD/arch-api#4 and CliXiD/arch-web#4, linked to each other.
- Round 2: both branches are rebased onto `origin/main`, which now includes job 002's model endpoints. The arch-api conflicts are resolved so both sides' behaviour is kept. `api/openapi.yaml` and `src/api/schema.d.ts` are regenerated, and both branches are force-pushed.

## Changes
### arch-api
- `internal/auth/principal.go`: service only when `ClientID != "" && ClientID == AuthorizedParty`. Removed the `service-account-` prefix check and the `azp` fallback, and dropped the `strings` import. Updated the doc comment.
- `internal/auth/principal_test.go`: changed the old "username without client_id uses azp" case to a user case. Added the `client_id != azp` and empty `client_id` cases.
- `internal/auth/jwks.go`: reworked `keySet`.
  - `mu` guards only `jwksURL`, `keys`, `loaded`, `lastAttempt`, `failed` and `lastRefetch`.
  - A cached `kid` returns at once.
  - Otherwise the caller joins `singleflight.Group.Do("jwks")`. `refresh` re-checks `mayFetch` under the lock, records the attempt, releases the lock, then runs discovery and the JWKS GET on `context.WithoutCancel`. It writes the result back under the lock. A failure leaves `keys` and `loaded` as they were.
  - After a fetch, or when no fetch is allowed, the caller looks the `kid` up again. It returns `errKeysUnavailable` when the keys were never loaded and `errUnknownKey` otherwise.
  - New exported `FailureBackoff = 5 s`. After a failed attempt only the 5 s backoff applies. Otherwise, once the keys are loaded, refetches follow the 30 s `RefetchInterval`. This is the only reading that meets the spec's "after load: no fetch at +4 s, one at +5 s".
- `internal/auth/verifier.go`: new `ErrUnavailable`. `Verify` returns it when `errors.Is(err, errKeysUnavailable)` and `ErrUnauthenticated` for everything else. Doc comments updated.
- `internal/auth/authtest/authtest.go`: added three switches, all applied to both discovery and JWKS. The existing API is unchanged.
  - `SetDown(bool)` makes the endpoints answer 503.
  - `Block() (release func())` holds requests until released. A JWKS request is counted when it starts.
  - `Arrived()` is a channel that receives once per request held by `Block`, so tests can order goroutines without sleeps.
- `internal/auth/verifier_test.go`:
  - replaced `TestVerifierJWKSFetchErrorIsUnauthenticated` with `TestVerifierJWKSDownIsUnavailable` (a 404 JWKS URL, and down-then-up after +5 s with both a configured and a discovered URL);
  - added `TestVerifierFailureBackoff`, a table over first load and after load: +4 s gives no fetch, +5 s gives one, and the after-load failure is `ErrUnauthenticated`;
  - added `TestVerifierKnownKidDuringRefetch` and `TestVerifierConcurrentUnknownKidSharesOneFetch` (20 goroutines). The existing `TestVerifierUnknownKid` covers 29 s vs 30 s.
- `go.mod`: `golang.org/x/sync v0.24.0` is now a direct dependency (`go mod tidy` agrees).
- `internal/httpapi/api.go`:
  - new constants `ProblemAuthUnavailable` and `ProblemTooLarge`;
  - `accessMiddleware` maps `auth.ErrUnavailable` to `503` with `Retry-After: 5` (derived from `auth.FailureBackoff`) and the fixed detail "signing keys are not available yet; try again";
  - `register` adds `413` and `503` to `op.Errors` for `/api/v1/` operations;
  - `writeProblem` now delegates to the new shared `writeHTTPProblem(w http.ResponseWriter, ...)`.
- `internal/httpapi/bodylimit.go` (new): `MaxBodyBytes = 1 << 20` and the `bodyLimit()` gin middleware.
  - A `Content-Length` over the limit gets `413` without reading the body.
  - A chunked body is read through `http.MaxBytesReader` into memory. Going over the limit gives `413`, any other read error gives a plain `400`, and otherwise `r.Body` is replaced with the buffer.
  - A known length within the limit is wrapped in `MaxBytesReader`.
  - The doc comment notes the future 5 MB import exemption.
- `internal/httpapi/engine.go`: registers `bodyLimit()` after the request logger and CORS. Since the round 2 rebase it sits before main's gzip middleware for `GET /api/v1/graph`, and `NewAPI` follows.
- `internal/httpapi/serve.go`: new `newServer(addr, h)` with the named constants `ReadHeaderTimeout` 10 s, `ReadTimeout` 30 s, `WriteTimeout` 30 s and `IdleTimeout` 120 s. Both servers use it.
- `internal/httpapi/serve_test.go` (new, internal package): `TestNewServerTimeouts`.
- `internal/httpapi/httpapi_test.go`:
  - `TestAuthUnavailable`: realm down from start, injected clock. Checks the 503 problem, `Retry-After` and that the token is not in the body, at +0 and +4 s. Requests without a token stay 401. The request answers 200 after the realm comes up and +5 s.
  - `TestBodyLimit`: POST and GET × `/api/v1/me` and `/healthz` × exactly 1 MB, 1 MB chunked, 1 MB+1 with `Content-Length`, and 1 MB+1 chunked.
- `internal/httpapi/registry_test.go`: the registry check now also requires `413` and `503` on `/api/v1` operations.
- `api/openapi.yaml`: regenerated with `make openapi`. After the rebase, `413` and `503` are on `/api/v1/me` and on every model endpoint from job 002 (8 × `"413"`; 9 × `"503"`, which includes the existing `/readyz` one).
- `README.md`: the Endpoints section lists the 503 and 413 problems, a line on the server timeouts, and the `client_id` == `azp` service-account rule with the mapper note.

### arch-web
- `src/api/me.ts`: `ApiError(status, problemType?)`. `useMe` passes `error?.type` when it is a string. New `isAuthUnavailable(err)`.
- `src/auth/context.ts`: `AuthState` gains `sessionRejected`, `apiUnauthorized` and `signInAgain`, with doc comments. The `reauthenticate` comment now says silent refresh.
- `src/auth/AuthProvider.tsx`:
  - exported constants `reauthKey = "arch.reauth.at"` and `reauthWindowMs = 60_000`;
  - `apiUnauthorized` does nothing without a user. A missing, non-finite or ≥60 s old timestamp writes `Date.now()` and re-authenticates; a fresher one sets `sessionRejected`. Before calling `reauthenticate()` it sets the user to null synchronously, so other 401s from the same page are ignored as the spec's assumption requires;
  - `signInAgain` writes the timestamp, calls `removeUser`, clears `sessionRejected`, sets the user to null and calls `signIn(returnTo)`;
  - `signIn` is now a `useCallback`. The silent-renew path still uses `reauthenticate`, unchanged.
- `src/api/ApiProvider.tsx`: `onUnauthorized: () => apiUnauthorized()`. `apiUnauthorized` is a stable `useCallback`, which the spec allows. The ref variant was rejected by the configured `react-hooks/refs` lint rule.
- `src/api/client.ts`: updated the `onUnauthorized` doc comment.
- `src/components/StatusMessage.tsx`: new `SessionRejected({ onSignInAgain, onSignOut })`, a full-page `role="alert"` with "Sign in again" and "Sign out" buttons using `buttonClass`.
- `src/auth/RequireAuth.tsx`:
  - renders `SessionRejected` when `sessionRejected` is true (after the "Signing out…" check, before children);
  - `needsSignIn` excludes `sessionRejected`;
  - "Sign in again" marks the current attempt as started, so the guard's effect does not start a second redirect. A rejected `signInAgain` shows `SignInUnavailable`.
- `src/components/Shell.tsx`: `isAuthUnavailable(me.error)` gives the full-page `SignInUnavailable` with `onRetry` set to `me.refetch()`. It sits after the 403 branch and before the generic error.
- `src/api/schema.d.ts`: regenerated with `pnpm gen:api` from `../arch-api/api/openapi.yaml`. In round 2 it was regenerated against the rebased arch-api, so the model operations also get `413` and `503`.
- `src/App.test.tsx`: the old single 401 test is replaced by five session tests (first 401, 401 within 60 s with both buttons, Sign out from the rejected state, a failed Sign in again, 401 after 60 s). Each one asserts that no test token is in `sessionStorage`. Two shell tests cover 503 auth-unavailable with Try again, and a 503 of another type.
- `README.md`: new "Session" section.
- `src/api/client.test.ts`: unchanged, because the client's options did not change.

No other repos are in the job. No change to `arch-deploy` or the hub realm, per the spec.

## Acceptance criteria
1. [x] [arch-api] `go test -count=1 -run 'TestPrincipalFromClaims' ./internal/auth/...` passes. The cases are: client credentials (`client_id == azp`) is a service with subject and name `arch-ci-platform`; a `service-account-` username without `client_id` is a user; `client_id != azp` is a user; an empty `client_id` with `azp` is a user. `grep -n 'service-account-' internal/auth/principal.go` finds nothing.
2. [x] [arch-api] `go test -count=1 -race -run 'TestVerifier' ./internal/auth/...` passes, and also passes with `-count=30 -race` (no flakes). It includes `TestVerifierKnownKidDuringRefetch`: a known kid authenticates while the k2 refetch is held by `Block`. It also includes `TestVerifierConcurrentUnknownKidSharesOneFetch`: 20 goroutines, `Fetches()` goes up by exactly 1, and all succeed.
3. [x] [arch-api] The same run has these fake-clock tests:
   - `TestVerifierUnknownKid/second unknown kid within 30 s no refetch`: no fetch at +29 s, one at +30 s.
   - `TestVerifierFailureBackoff/{failed first load, failed refetch after load}`: no fetch at +4 s, one at +5 s.
   - `TestVerifierJWKSDownIsUnavailable`: `ErrUnavailable` while down, then success once the realm is up and +5 s have passed.
4. [x] [arch-api] `go test -count=1 ./internal/httpapi/...` passes. In `TestAuthUnavailable`, a token gets `503`, `application/problem+json`, `Retry-After: 5` and type `/problems/auth-unavailable`, and the body does not contain the token. After the realm comes up and +5 s, the same request gives `200`. Without a token it stays `401`.
5. [x] [arch-api] `TestBodyLimit` passes: 1 MB+1 with `Content-Length` and 1 MB+1 chunked both give `413` with type `/problems/too-large`, and exactly 1 MB is not `413`. It runs on POST and GET for `/api/v1/me` and `/healthz`. `TestNewServerTimeouts` asserts 10/30/30/120 s.
6. [x] [arch-api] `api/openapi.yaml` has `"413"` and `"503"` under `/api/v1/me` (lines 28 and 40; line 80 is the existing `/readyz` 503). The criterion's grep uses single quotes and `auth-unavailable`, but the generated YAML uses double-quoted keys and does not model problem types, so I grepped `"413"\|"503"`. `make openapi-check` exits 0.
7. [x] [arch-api] Manual check on the local stack (Keycloak with the re-imported realm), running `go run ./cmd/arch-api serve` from the worktree on `127.0.0.1:5190`:
   - The `arch-ci-platform` client-credentials token carries `client_id`, `azp` = `arch-ci-platform` and the username `service-account-arch-ci-platform`. `GET /api/v1/me` → `200 {"subject":"arch-ci-platform","name":"arch-ci-platform","email":"","roles":["viewer","editor"],"teams":["platform"],"actor_kind":"service"}`.
   - The `editor` browser token comes from an authorization code + PKCE flow against `arch-web`, driven with curl and the dummy `editor`/`password` (no `client_id` claim, `azp` = `arch-web`). → `200 ... "name":"Editor Local" ... "actor_kind":"user"`.
   - Keycloak unreachable: instead of stopping the shared Keycloak, I started a second `serve` with `OIDC_JWKS_URL=http://127.0.0.1:9/jwks` (refused port). This hits the same never-loaded path. The token got `HTTP/1.1 503`, `Content-Type: application/problem+json`, `Retry-After: 5` and the auth-unavailable body. No token gave `401`. A 1,048,577-byte POST to `/healthz` gave `413` with `/problems/too-large`. The token does not appear in the server log.
   - Both servers were stopped by their PID on port 5190.
8. [x] [arch-api] `README.md` mentions `/problems/auth-unavailable` (with `Retry-After: 5`), `/problems/too-large` (1 MB, every route), the 10 s read-header and 30/30/120 s timeouts, and the `client_id` == `azp` rule with the mapper note.
9. [x] [arch-web] `pnpm run test` passes (30 tests). It covers:
   - a first 401 gives one `signinRedirect` with `returnTo` and sets `arch.reauth.at`;
   - a 401 within 60 s shows the rejected text and both buttons, with no `signinRedirect`;
   - "Sign in again" calls `signinRedirect` exactly once;
   - "Sign out" calls `signoutRedirect`;
   - a 401 older than 60 s redirects;
   - every session test asserts that no `sessionStorage` key or value contains the test tokens.
10. [x] [arch-web] "shows Sign-in is unavailable on 503 auth-unavailable, and Try again refetches": the alert text is right, there is no banner, and clicking "Try again" makes the second call to `http://api.test/api/v1/me`. A 503 of another type still shows "Couldn't load your profile".
11. [x] [arch-web] Running `pnpm gen:api` again after the commit leaves `git status` clean. The diff adds `413` and `503` to `get-me`. `pnpm run typecheck` passes.
12. [x] [arch-web] The `README.md` "Session" section covers the 60 s cap, the `arch.reauth.at` timestamp (no token or claim) and the 503 state.

UI note: I did no browser check. The realm's `arch-web` client accepts redirects to `http://localhost:5173/*` only, so a dev server on the job port 5191 cannot sign in. The states are covered by the Testing Library tests above.

## Validation
Round 2 (after the rebase onto `origin/main` at arch-api `d91438b`):
- arch-api: `make openapi` regenerated the spec and was committed in the rebased feat commit. `go mod tidy` made no change. The `arch-api.sh` check passed (golangci-lint 0 issues, go test, go build, `make openapi-check`). `go test -count=1 -race ./internal/auth/... ./internal/httpapi/` passed. The branch head is `f2622ac`.
- arch-web: under Node 26, `pnpm gen:api` followed by a fixup into the `chore: regenerate API types` commit. The `arch-web.sh` check passed (lint, typecheck, 30 tests, build). Running `pnpm gen:api` again gives no diff. The branch head is `0031c52`.
- I did not repeat the manual stack check from criterion 7. The rebase only touched how the conflicting lines were merged, and the tests above cover the behaviour.

Round 1:
### arch-api
- `FACTORY_HUB=... FACTORY_REPO_KEY=arch-api FACTORY_BASE=origin/main bash factory/checks/arch-api.sh`: pass (go vet, golangci-lint 0 issues, go test, go build, make openapi-check).
- `go test -count=1 -race ./internal/auth/... ./internal/httpapi/`: pass.
- `go test -count=30 -race -run TestVerifier ./internal/auth/`: pass.
- `go mod tidy`: no further change to go.mod or go.sum.
- Manual stack check: see criterion 7.
### arch-web
- `FACTORY_HUB=... FACTORY_REPO_KEY=arch-web FACTORY_BASE=origin/main bash factory/checks/arch-web.sh`: pass (lint, typecheck, 30 tests, build).
- `pnpm gen:api` again after the commit: no diff.

## Log
### Round 1
- Implemented arch-api requirements 1–11 and arch-web requirements 1–8.
- arch-api commits:
  - `fix: treat a token as a service account only when client_id equals azp`
  - `fix: fetch JWKS outside the lock, share one fetch and back off after failures`
  - `feat: answer 503 auth-unavailable and 413 too-large, add server timeouts`
  - `docs: document new problems, timeouts and the service-account rule`
- arch-web commits:
  - `chore: regenerate API types with 413 and 503 problems`
  - `fix: cap automatic sign-in after a 401 and show auth-unavailable on 503`
  - `docs: describe the re-sign-in cap and the auth-unavailable state`
- Choices worth a reviewer's look:
  - After a failed fetch, the 5 s backoff applies instead of the 30 s refetch interval. Applying both would block the "after load, +5 s" fetch the spec requires.
  - `apiUnauthorized` drops the in-memory user synchronously before `reauthenticate()`, so concurrent 401s are ignored as the spec's assumption asks.
  - The chunked-body read error that is not a size error answers a plain `400`. The spec does not cover this case.
  - `ApiProvider` passes the stable `apiUnauthorized` callback; the configured lint rule rejects the ref pattern.
- I ran `dev/bin/apply-env --to <arch-api worktree> arch-api` for the manual check. The `.env` is gitignored, and both worktrees are clean.
- Draft PRs: https://github.com/CliXiD/arch-api/pull/4 and https://github.com/CliXiD/arch-web/pull/4, cross-linked under Related PRs.
- High risk (token validation, access middleware): the Factory notes say this always escalates to a human.

### Round 2
- Feedback 1 (@CliXiD): rebase onto main and resolve the conflicts. Done.
- arch-api: `git rebase origin/main`. Commit `feat: answer 503 auth-unavailable and 413 too-large, add server timeouts` conflicted in two files:
  - `internal/httpapi/api.go`: I kept main's `ProblemNotFound` and `ProblemValidation` constants and `newProblem` (huma.NewError), and added this job's `ProblemAuthUnavailable` and `ProblemTooLarge`, the `ErrUnavailable` → 503 mapping and `writeHTTPProblem`.
  - `internal/httpapi/engine.go`: I kept both middlewares in the order `bodyLimit()`, then main's `gzip` (graph only), then `NewAPI`, and merged the doc comment to match. The body limit checks requests before anything else runs, and its 413 does not go through the gzip writer.
  - `api/openapi.yaml`: regenerated with `make openapi`, not hand-merged.
  - The other three commits rebased cleanly. I force-pushed with `--force-with-lease`.
- arch-web: `git rebase origin/main` went through cleanly. I regenerated `src/api/schema.d.ts` against the rebased arch-api spec (126 more lines for the model operations' 413/503) and folded it into the existing `chore: regenerate API types` commit with a fixup and autosquash. Force-pushed with `--force-with-lease`.
- Both PRs (CliXiD/arch-api#4 and CliXiD/arch-web#4) are open against `main`. arch-api#4 now reports MERGEABLE. Both are already marked ready for review, and I left that state as it was.
- Both worktrees are clean.

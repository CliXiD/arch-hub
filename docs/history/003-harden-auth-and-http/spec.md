# Harden auth and HTTP server after the walking skeleton

> Issue #7: Harden auth and HTTP server after the walking skeleton

## Summary
- Fixes review notes 1, 2, 3 and 6 of job 001 before the write slice (#5) starts recording `actor_kind` in `change_log` ([NFR-003]).
- `arch-api`: a token is a service account only when `client_id` == `azp` ([SPEC-identity-access-07]). The JWKS cache fetches outside its lock, shares one fetch between concurrent callers, and backs off. The API returns `503 /problems/auth-unavailable` while it has never loaded signing keys ([SPEC-identity-access-02]). The servers get read, write and idle timeouts, and every route gets a 1 MB body limit that answers `413 /problems/too-large`.
- `arch-web`: a `401` triggers at most one automatic sign-in per 60 s, and a second one shows a "session rejected" state. A `503 auth-unavailable` shows the existing "Sign-in is unavailable" state.
- `api/openapi.yaml` and `src/api/schema.d.ts` are regenerated. The hub's dev realm already has the `client_id` mapper, and `arch-deploy` does not change.
- High risk: this changes token validation and the access middleware, which the Factory notes always escalate.

## Context

### arch-api
- `arch-api:internal/auth/principal.go`: `PrincipalFromClaims` makes a token a service account when `c.ClientID != ""` **or** `preferred_username` starts with `service-account-`, and falls back to `azp` for the id. `Claims` already decodes `client_id` and `azp`. Tests: `arch-api:internal/auth/principal_test.go` (table-driven). Its case "service-account username without client_id uses azp" encodes the behaviour this job removes.
- `arch-api:internal/auth/jwks.go`: `keySet.get` takes `s.mu` for the whole call, including `fetch()`, which does OIDC discovery plus the JWKS GET through `s.client` (the 5 s timeout `http.Client` from `NewVerifier`). Before `loaded` is true, every call fetches with no rate limit. After that, `RefetchInterval` (30 s) limits unknown-`kid` refetches through `lastRefetch`. `s.now` is the injectable clock (`auth.Options.Now`).
- `arch-api:internal/auth/verifier.go`: `Verify` turns every parser or keyfunc error into `ErrUnauthenticated`. golang-jwt v5 wraps the keyfunc error, so `errors.Is` reaches it. `Authenticate` returns `ErrUnauthenticated` for a missing or non-Bearer header before any key lookup.
- `arch-api:internal/auth/authtest/authtest.go`: a fake realm (`Realm`) with discovery, a JWKS endpoint that counts fetches (`Fetches()`), `SetKeys`, `Claims` and `Sign`. Tests: `arch-api:internal/auth/verifier_test.go` uses a settable `clock`. `TestVerifierJWKSFetchErrorIsUnauthenticated` asserts the behaviour this job changes.
- `arch-api:internal/httpapi/api.go`: `register` adds bearer security and `op.Errors` 401/403 to every `/api/v1/` operation. `accessMiddleware` maps any `Authenticate` error to `401 /problems/unauthenticated`. `writeProblem` writes an RFC 9457 `huma.ErrorModel` with a fixed `detail`. The problem types are constants (`ProblemUnauthenticated`, `ProblemForbidden`).
- `arch-api:internal/httpapi/engine.go`: `NewEngine` builds the gin chain (recovery, otelgin, metrics, request log, CORS) and then calls `NewAPI`. No operation reads a request body today; `GET /api/v1/me` is the only `/api/v1` route.
- `arch-api:internal/httpapi/serve.go`: both `http.Server`s (API on `HTTP_ADDR`, metrics on `METRICS_ADDR`) are built inline with only `ReadHeaderTimeout: 10 * time.Second`.
- `arch-api:internal/httpapi/httpapi_test.go`: `newTestServer`, `do`, `bearer` and `problem` helpers. `TestProblems` is table-driven over status, type and detail.
- `golang.org/x/sync` is already in `go.mod` as an indirect dependency, so `singleflight` is available.
- `make openapi` / `make openapi-check` (`arch-api:Makefile`). `arch-api:README.md` documents the endpoints and problems.

### arch-web
- `arch-web:src/api/client.ts`: `createApiClient` calls `onUnauthorized()` on every `401`. `arch-web:src/api/ApiProvider.tsx` wires that to `useAuth().reauthenticate`.
- `arch-web:src/auth/AuthProvider.tsx`: `reauthenticate` runs `client.removeUser()` and `setUser(null)`, and `RequireAuth` (`arch-web:src/auth/RequireAuth.tsx`) then calls `signIn(returnTo)` (`signinRedirect`). The silent-renew error handler uses the same `reauthenticate`. Every `401` therefore causes a new redirect, so a persistent `401` loops.
- `arch-web:src/auth/context.ts`: the `AuthState` type.
- `arch-web:src/api/me.ts`: `ApiError` carries only `status`, and `useMe` throws `new ApiError(response.status)` without reading the problem body.
- `arch-web:src/components/Shell.tsx`: on `403` it shows the full-page no-access message (with `StatusMessage` and `buttonClass`). Any other error shows "Couldn't load your profile" with "Try again", which is where a `503` lands today.
- `arch-web:src/components/StatusMessage.tsx`: `StatusMessage`, `buttonClass` and `SignInUnavailable({ onRetry })` ("Sign-in is unavailable, try again" plus "Try again").
- Tests: `arch-web:src/App.test.tsx` (describe "session", including "signs in again ... when the API answers 401") and `arch-web:src/api/client.test.ts`. The helpers in `arch-web:src/test/fakeAuth.ts` are `fakeAuthClient`, `testUser`, `stubMe(status, body)` and `editorMe`. `arch-web:src/test/setup.ts` clears `sessionStorage` after each test. `arch-web:src/auth/userManager.test.ts` asserts that no token is in `sessionStorage`.
- `pnpm gen:api` reads `../arch-api/api/openapi.yaml`, which is the sibling worktree inside this job.

### hub
- `dev/keycloak/arch-realm.json` already gives `arch-ci-platform` the `client_id` protocol mapper (user session note `clientId`). The hub needs no change.

## Contract

**`GET /api/v1/me`**: the response shape is unchanged ([SPEC-identity-access-08]).
- `actor_kind` is `"service"` if and only if the token has a non-empty `client_id` claim equal to `azp`. Then `subject` and `name` are that client id and `email` is the token's (normally empty).
- Every other token gets `actor_kind: "user"`, with `subject` = `sub` and `name` = `name`, or `preferred_username` when `name` is empty. This holds even when `preferred_username` starts with `service-account-`.

**New problem types** (RFC 9457, `Content-Type: application/problem+json`, body `huma.ErrorModel` `{type, title, status, detail}`; `detail` is fixed text, never a token, claim or header value):

| status | type | when | headers | example body |
|---|---|---|---|---|
| 503 | `/problems/auth-unavailable` | any `/api/v1` operation whose bearer token reaches the key lookup while the API has never loaded the signing keys (the fetch fails now, or is held back by the 5 s backoff) | `Retry-After: 5` | `{"type":"/problems/auth-unavailable","title":"Service Unavailable","status":503,"detail":"signing keys are not available yet; try again"}` |
| 413 | `/problems/too-large` | a request body larger than 1 MB (1,048,576 bytes) on any route of the API server | — | `{"type":"/problems/too-large","title":"Request Entity Too Large","status":413,"detail":"request body exceeds 1 MB"}` |

**Status precedence:**
- A missing, non-Bearer or malformed token stays `401 /problems/unauthenticated`, because it fails before any key lookup.
- Once keys have been loaded:
  - an unknown `kid` that is still unknown after the allowed refetch is `401`;
  - an unknown `kid` inside the 30 s window is `401`;
  - a failed refetch is `401`.
- A body over 1 MB is `413` before authentication runs.

**OpenAPI:** every `/api/v1/` operation lists the error responses `401`, `403`, `413` and `503` (ErrorModel). `/healthz` and `/readyz` are unchanged.

**Web interpretation:**
- `503` with `type == "/problems/auth-unavailable"` means "Sign-in is unavailable, try again", and "Try again" refetches.
- `401` follows the capped re-sign-in rule below.
- Every other error keeps its current handling.

**Web `sessionStorage`:** one key, `arch.reauth.at`, whose value is the epoch milliseconds of the last automatic sign-in after a `401`. It never holds a token or a claim.

**Env vars:** none added. **Schema:** none.

**Keycloak:** every CI client needs a `client_id` mapper (type user session note, note `clientId`, claim `client_id`, access token). The dev realm already has it. The `arch-deploy` realm export must carry it when that export is created (not in this job).

**Compatibility:**
- The `me` shape is unchanged, and the new statuses only add to the documented responses.
- The deployed web app treats `503` as a generic error ("Couldn't load your profile", "Try again") until the new `arch-web` ships, which is safe.
- The only behaviour change for existing callers is that a username-prefixed token without `client_id` becomes a user. No writer of `actor_kind` exists yet (#5 is blocked by this job).

## Requirements

### arch-api
1. `PrincipalFromClaims` (`internal/auth/principal.go`) returns `ActorService` only when `c.ClientID != "" && c.ClientID == c.AuthorizedParty`, with `Subject` and `Name` set to `c.ClientID`. The `service-account-` prefix check and the `azp` fallback are removed, and the doc comment is updated. Update the table test in `principal_test.go`:
   - `client_id` == `azp` gives a service with the client id as subject and name;
   - `preferred_username: service-account-x` without `client_id` gives a user (name falls back to the username);
   - `client_id` ≠ `azp` gives a user;
   - an empty `client_id` with any `azp` gives a user.
2. Rework `keySet` in `internal/auth/jwks.go`:
   - **Lock scope.** `mu` guards only the in-memory state (`keys`, `loaded`, the last-attempt time, whether the last attempt failed). It is never held during discovery or any HTTP call. A lookup for a `kid` already in `keys` returns at once, even while a fetch is in flight.
   - **Single flight.** Every fetch (first load and unknown-`kid` refetch) runs through one `golang.org/x/sync/singleflight.Group` (or an equivalent hand-written in-flight channel). Concurrent callers join the fetch in flight instead of starting another. Promote `golang.org/x/sync` to a direct dependency in `go.mod` if it is used.
   - **Shared context.** The shared fetch must not be cancelled by the joining request that started it. Run it with `context.WithoutCancel(ctx)`; the `http.Client` 5 s timeout still bounds it.
   - **Backoff.** A fetch starts only when:
     - (a) after a failed attempt, at least `FailureBackoff` = 5 s (new exported constant) has passed since that attempt;
     - (b) for an unknown-`kid` refetch once keys are loaded, at least `RefetchInterval` = 30 s has passed since the last refetch attempt.
     Both apply to the first load too, so a failed first fetch blocks new fetches for 5 s. Time comes from `s.now`, so tests stay deterministic.
   - **Lookup order.** When a fetch is not allowed, or after a fetch completes, the caller looks the `kid` up again in the current `keys` before giving up. A caller that arrives just after a rotation fetch still finds the new key.
   - **Failed fetch.** A failed fetch leaves the previously loaded `keys` and `loaded` state untouched. A successful fetch replaces `keys` and sets `loaded`. Discovery also runs inside the shared fetch, and its result (`jwksURL`) is written under the lock.
   - **Errors.** Return an internal `errKeysUnavailable` when the keys have never been loaded and no key could be obtained (the fetch failed, or the backoff held it back). Otherwise return `errUnknownKey`.
3. In `internal/auth/verifier.go`, add the exported `ErrUnavailable` ("signing keys are not available", no token or claim values). `Verify` and `Authenticate` return `ErrUnavailable` when the keyfunc error `errors.Is(err, errKeysUnavailable)`, and `ErrUnauthenticated` for every other failure (unchanged). Update the doc comments.
4. Extend `internal/auth/authtest/authtest.go` so tests can make the JWKS endpoint:
   - fail with `503` (e.g. `SetDown(bool)`);
   - block until released (e.g. `Block() (release func())`), counting a fetch when it starts.
   Discovery uses the same switches. Keep the existing API.
5. Add tests in `internal/auth/verifier_test.go`, table-driven where cases share a shape:
   - With the JWKS blocked mid-refetch for an unknown `kid`, a token with a known `kid` authenticates before the fetch is released.
   - 20 goroutines with the same unknown `kid` cause exactly one JWKS fetch and all succeed after release (keys rotated to include it).
   - Unknown-`kid` refetches are limited to one per 30 s on the fake clock: 29 s gives no fetch, 30 s gives a fetch.
   - After a failed fetch (first load, and after load), no new fetch starts at +4 s and one starts at +5 s.
   - With the JWKS down from the start, `Authenticate` returns `ErrUnavailable`. After it comes up and 5 s pass, the same token succeeds.
   - Once loaded, a fetch failure on an unknown `kid` is `ErrUnauthenticated`, not `ErrUnavailable`.
   - Replace `TestVerifierJWKSFetchErrorIsUnauthenticated` with the `ErrUnavailable` expectation.
   - Run the new tests under `-race` locally. Use `sync` primitives, not sleeps, to order the goroutines.
6. In `internal/httpapi/api.go`, add the constants `ProblemAuthUnavailable = "/problems/auth-unavailable"` and `ProblemTooLarge = "/problems/too-large"`. In `accessMiddleware`, `errors.Is(err, auth.ErrUnavailable)` sets `Retry-After: 5` and writes a `503` problem of that type with a fixed detail. Every other error stays `401`. `register` adds `http.StatusRequestEntityTooLarge` and `http.StatusServiceUnavailable` to `op.Errors` for `/api/v1/` operations.
7. Add a gin middleware in `internal/httpapi` (e.g. `bodylimit.go`, constant `MaxBodyBytes = 1 << 20`) and register it in `NewEngine` after the request logger and CORS and before `NewAPI`, so every route gets it:
   - A request whose `Content-Length` exceeds `MaxBodyBytes` is aborted with a `413 /problems/too-large` problem and its body is not read.
   - A request with an unknown length (chunked) is read through `http.MaxBytesReader` into memory, up to the limit. Exceeding it gives the same `413`. Otherwise `r.Body` is replaced with the buffered bytes.
   - A body of known length within the limit is wrapped in `http.MaxBytesReader`.
   Write the problem with the same `huma.ErrorModel` encoding as `writeProblem`, sharing one helper so the shape cannot drift. Add a doc comment saying that a route with a larger documented limit (the YAML import, 5 MB, [SPEC-yaml-as-code-03]) will exempt itself here when it is added.
8. In `internal/httpapi/serve.go`, build both servers through one helper (e.g. `newServer(addr string, h http.Handler) *http.Server`) with `ReadHeaderTimeout` 10 s (kept), `ReadTimeout` 30 s, `WriteTimeout` 30 s and `IdleTimeout` 120 s as named constants.
9. Add tests in `internal/httpapi`:
   - Server config: `newServer` sets the four timeouts.
   - Body limit, table-driven (`POST` and `GET` on `/api/v1/me` and `/healthz`):
     - a body of exactly 1 MB is not `413`;
     - 1 MB + 1 byte with `Content-Length` is `413 /problems/too-large` with `application/problem+json`;
     - 1 MB + 1 byte chunked (`ContentLength = -1`) is also `413`.
   - Problems: `TestProblems` (or a sibling test) shows that a JWKS that is down from start-up gives `503 /problems/auth-unavailable` with `Retry-After: 5` and a body without the token, and that the same request answers `200` once the JWKS is up and the backoff has passed (injected clock via `auth.Options.Now`). Requests without a token in that state stay `401`.
10. Run `make openapi` and commit the regenerated `api/openapi.yaml`, with `413` and `503` listed for `/api/v1/me`.
11. Update `README.md`:
    - the Endpoints section lists `503 /problems/auth-unavailable` (`Retry-After: 5`) and `413 /problems/too-large` (1 MB, every route);
    - add a line on the server timeouts;
    - add a line saying that a service account is a token whose `client_id` equals `azp` (CI clients need the `client_id` mapper).

### arch-web
1. In `src/api/me.ts`, `ApiError` gains an optional `problemType?: string` (constructor `(status, problemType?)`). `useMe` reads `error` from the `openapi-fetch` result and passes `error?.type` when it is a string. Export a helper `isAuthUnavailable(err: unknown): boolean` (`ApiError`, status `503`, type `/problems/auth-unavailable`).
2. In `src/auth/AuthProvider.tsx` and `src/auth/context.ts`, add to `AuthState`:
   - `sessionRejected: boolean`;
   - `apiUnauthorized: () => void`. It does nothing when there is no current user (`userRef.current` is null, e.g. a redirect is already under way). Otherwise it reads `sessionStorage["arch.reauth.at"]`:
     - When the key is missing, not a finite number, or 60 s or more old, it writes `String(Date.now())` and calls `reauthenticate()`, which redirects as today.
     - Otherwise it sets `sessionRejected` to true and does not redirect.
   - `signInAgain: (returnTo: string) => Promise<void>`. It writes `arch.reauth.at = now`, clears `sessionRejected`, runs `client.removeUser()` and `setUser(null)`, and calls `signIn(returnTo)`.
   Keep the 60 s window as a named constant. `sessionStorage` holds only that timestamp. The silent-renew error path keeps using `reauthenticate` unchanged. Update the `AuthState` doc comments.
3. `src/api/ApiProvider.tsx` passes `onUnauthorized: () => auth.apiUnauthorized()`, through a ref or a stable callback so the client created once in `useState` always calls the current function. Update the `onUnauthorized` doc comment in `src/api/client.ts`.
4. When `sessionRejected` is true, `src/auth/RequireAuth.tsx` renders, in place of its children, a full-page `StatusMessage role="alert"` with:
   - the text "Your session was rejected by the API. Try signing in again.";
   - a "Sign in again" button that calls `signInAgain(returnTo)`; a rejected `signIn` shows `SignInUnavailable` as the existing flow does;
   - a "Sign out" button that calls `signOut()`.
   Use `buttonClass`. Put the component in `src/components/StatusMessage.tsx` next to `SignInUnavailable` (e.g. `SessionRejected`).
5. In `src/components/Shell.tsx`, when `isAuthUnavailable(me.error)` is true, render `<SignInUnavailable onRetry={() => void me.refetch()} />` (full page) before the generic error branch. The `403` and other-error branches are unchanged.
6. Run `pnpm gen:api` against the job's `../arch-api/api/openapi.yaml` (after arch-api requirement 10) and commit `src/api/schema.d.ts`. Never hand-edit it.
7. Add tests, querying by role and text:
   - In `src/App.test.tsx`: a first `401` from `/me` gives exactly one `signinRedirect` with the current route and sets `arch.reauth.at`.
   - A `401` with `arch.reauth.at` set to `Date.now() - 10_000` before render shows the rejected message and both buttons, with no `signinRedirect`. "Sign in again" calls `signinRedirect`, and "Sign out" calls `signoutRedirect`.
   - A `401` with `arch.reauth.at` older than 60 s redirects again.
   - After these flows, no `sessionStorage` value contains `test-access-token`, `test-id-token` or `test-refresh-token`.
   - A `503` `{type:"/problems/auth-unavailable"}` from `/me` shows "Sign-in is unavailable, try again", and "Try again" calls `/api/v1/me` again.
   - Another `503` (other type) still shows "Couldn't load your profile".
   Update `src/api/client.test.ts` only if the client's options change.
8. Update `README.md`: a short "Session" note on the capped re-sign-in (60 s, `sessionStorage` key `arch.reauth.at`, timestamp only) and the `503 auth-unavailable` state.

## Acceptance criteria
1. [arch-api] `cd <arch-api worktree> && go test -count=1 -run 'TestPrincipalFromClaims' ./internal/auth/...` passes. The table includes the cases `client_id == azp` (service, subject and name = client id), `service-account-` username without `client_id` (user) and `client_id != azp` (user). `grep -n 'service-account-' internal/auth/principal.go` finds nothing.
2. [arch-api] `go test -count=1 -race -run 'TestVerifier' ./internal/auth/...` passes. It includes:
   - a test where a known-`kid` token authenticates while a blocked unknown-`kid` refetch is in flight;
   - a test where 20 concurrent same-unknown-`kid` requests give `realm.Fetches()` up by exactly 1.
3. [arch-api] The same run includes fake-clock tests:
   - no refetch at +29 s and one at +30 s for unknown `kid`s;
   - after a failed fetch, no fetch at +4 s and one at +5 s, both on first load and after load;
   - JWKS down from start gives `errors.Is(err, auth.ErrUnavailable)`, and it is up and +5 s later gives success.
4. [arch-api] `go test -count=1 ./internal/httpapi/...` passes. It includes:
   - JWKS down from start-up: `GET /api/v1/me` with a well-formed bearer token gives `503`, `Content-Type: application/problem+json`, `Retry-After: 5` and body `type` `/problems/auth-unavailable`. After the realm comes up and the clock passes 5 s, the same request gives `200`.
   - The same state without a token gives `401`.
5. [arch-api] The same run includes:
   - a body-limit table: 1 MB + 1 byte with `Content-Length`, and chunked, each give `413` with `type: /problems/too-large`; exactly 1 MB is not `413`;
   - a test that asserts `ReadTimeout` 30 s, `WriteTimeout` 30 s, `IdleTimeout` 120 s and `ReadHeaderTimeout` 10 s on the server helper.
6. [arch-api] `grep -n "auth-unavailable\|'413'\|'503'" api/openapi.yaml` shows `413` and `503` responses under `/api/v1/me`, and `make openapi-check` exits 0.
7. [arch-api] Manual check against the local stack. Run `dev/bin/stack up` with the realm re-imported, then `go run ./cmd/arch-api serve` from the worktree.
   - A client-credentials token for `arch-ci-platform` (secret `dev-ci-secret`) on `GET /api/v1/me` gives `actor_kind: "service"`, with `subject` and `name` `arch-ci-platform`.
   - A password-grant or browser token for `editor` gives `actor_kind: "user"`.
   - With Keycloak stopped before `serve` starts, the call gives `503` with `Retry-After: 5`.
8. [arch-api] `README.md` mentions `/problems/auth-unavailable`, `/problems/too-large`, the 30/30/120 s timeouts and the `client_id` == `azp` rule.
9. [arch-web] `cd <arch-web worktree> && pnpm run test` passes, including:
   - a first `401` gives one `signinRedirect` with `returnTo`;
   - a second `401` within 60 s shows "Your session was rejected by the API. Try signing in again." with the buttons "Sign in again" and "Sign out", and `signinRedirect` is not called;
   - "Sign in again" calls `signinRedirect`, and "Sign out" calls `signoutRedirect`;
   - no `sessionStorage` value contains a test token.
10. [arch-web] The same run includes a test where a `503` `/problems/auth-unavailable` from `/me` shows "Sign-in is unavailable, try again" with "Try again", and clicking it requests `/api/v1/me` again.
11. [arch-web] `src/api/schema.d.ts` is identical to the output of `pnpm gen:api` run against the job's `../arch-api/api/openapi.yaml`, and it lists `413` and `503` for `/api/v1/me`. `pnpm run typecheck` passes.
12. [arch-web] `README.md` describes the 60 s re-sign-in cap, the `arch.reauth.at` timestamp and the `503` state.

## Merge and deploy order
1. **arch-api first** (`merge_order`). It defines the new problem types, and `api/openapi.yaml` must be merged before `arch-web` regenerates `schema.d.ts` from it. Deploying it alone is safe: the old web app shows a generic error on `503`.
2. **arch-web second**, regenerated from the merged `openapi.yaml`.
3. No `arch-deploy` change.

## Out of scope
- `arch-deploy`, including the realm export with the `client_id` mapper, Helm values and probes.
- CSP, security headers, ingress rules and making health or metrics private (review notes 4 and 7).
- Trace sampling (note 5).
- Any `.github/*` change, including pinning action SHAs (note 8; protected).
- The hub realm file `dev/keycloak/arch-realm.json`, which already has the mapper.
- Any model, write or import endpoint, and the 5 MB import override itself.
- Changing how the silent-renew failure re-authenticates.
- Making the limits or timeouts configurable (no new env vars).
- A proactive health probe of Keycloak at start-up.
- Retry or backoff logic in the web client beyond "Try again".
- Touching `change_log`, migrations or the DB.

## Assumptions
- `503` is returned only when a bearer token reaches the key lookup. Requests without a token, or with a malformed one, stay `401`. Reason: intake's Scope says so, and the caller cannot be helped by a retry in that case.
- `503` also covers a token that arrives inside the 5 s backoff before the first load, without a new fetch. Reason: the keys are still unavailable, so `401` would wrongly blame the token.
- After the keys have loaded once, a failed refetch gives `401`, not `503`. Reason: [SPEC-identity-access-02] limits `503` to "never loaded".
- The 1 MB limit applies to every route of the API server (including `/healthz`, `/readyz` and unmatched paths) and is checked before authentication. The metrics server reads no bodies and gets only the timeouts. Reason: Decision 5 says "every route".
- Chunked bodies are buffered (at most 1 MB) so the `413` is guaranteed even on routes that never read the body. Reason: intake asked for the `413` to hold for chunked bodies. This is bounded memory, and `ReadTimeout` caps slow senders.
- The OpenAPI lists `413` and `503` on `/api/v1` operations only, not on `/healthz` or `/readyz`, and the `Retry-After` header is not modelled in OpenAPI. Reason: smallest change. The health routes keep their documented shapes.
- The shared JWKS fetch runs on `context.WithoutCancel` of the triggering request. Reason: a client that disconnects must not fail the fetch for every request that joined it.
- 401s that arrive while no user is held (a redirect is already under way) are ignored. Reason: concurrent 401s from one page must not trip the "rejected" state on the first rejection.
- "Sign in again" records a new timestamp. Reason: if the API keeps rejecting, the user sees the rejected state again instead of starting a loop.
- The `sessionStorage` key name `arch.reauth.at`. Reason: the issue requires a timestamp but names no key.

## Docs impact
- `docs/specs/001_identity-access.md`, *Interfaces*: extend "Errors on every endpoint" with `503 /problems/auth-unavailable` (`Retry-After: 5`) and `413 /problems/too-large`.
- `docs/specs/001_identity-access.md`, [SPEC-identity-access-09]: add that a `401` from the API triggers at most one automatic sign-in per 60 s, after which the web app shows "Your session was rejected by the API. Try signing in again." with "Sign in again" and "Sign out".
- `docs/specs/009_operations.md`, *Non-functional* (or a new SPEC-operations item): the API server's read and write timeouts (30 s) and idle timeout (120 s), and the 1 MB default body limit with `413 /problems/too-large`, overridden per route only where a spec says so ([SPEC-yaml-as-code-03]).

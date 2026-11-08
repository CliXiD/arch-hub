DECISION: ACCEPT
RISK: high
SURFACES: ui, security
REPOS: arch-api, arch-web
RESCOPED: no

## Summary
- Accepted as written: fixes review notes 1, 2, 3 and 6 of job 001 in `arch-api` and `arch-web`, one PR each.
- The code confirms every weakness the issue names (service-account rule by username prefix, JWKS fetch under the lock with no backoff before the first load, `ReadHeaderTimeout` only, uncapped re-sign-in on `401`).
- The hub documents already carry the new rules ([SPEC-identity-access-02], [SPEC-identity-access-07]); the issue agrees with them, and the dev realm already has the `client_id` mapper, so no hub change is needed.
- Risk is high: it changes the auth middleware and token validation, which the Factory notes always escalate. `arch-deploy` does not change.

## Scope

**arch-api**
- Principal mapping: a token is a service account only when it has a `client_id` claim equal to `azp`; then `GET /api/v1/me` returns `actor_kind: "service"` with the client id as `subject` and `name`. Every other token is a user, whatever its `preferred_username` (today `principal.go` also accepts the `service-account-` prefix).
- JWKS cache: the discovery and JWKS HTTP calls run outside the cache lock, so a token with a known `kid` never waits on a fetch in progress; concurrent unknown-`kid` requests share one fetch (single-flight). An unknown-`kid` refetch happens at most once per 30 s; after any failed fetch, including the first, the next attempt waits at least 5 s. The clock stays injectable for tests.
- New problem `503 /problems/auth-unavailable` with `Retry-After: 5`: returned on every `/api/v1` operation for a request that carries a bearer token while the API has never loaded the signing keys. Requests without a token stay `401`, and once keys are loaded an unknown `kid` that is still unknown after a refetch stays `401`. This needs a distinct error from the verifier (today `verifier.go` folds every failure into `ErrUnauthenticated`) and a new branch in `accessMiddleware`.
- API server: `ReadTimeout` 30 s, `WriteTimeout` 30 s, `IdleTimeout` 120 s (keep `ReadHeaderTimeout`). Request bodies over 1 MB on any API route get `413 /problems/too-large`; the spec writer should settle how to guarantee the `413` for both declared `Content-Length` and chunked bodies (e.g. a size check plus `http.MaxBytesReader` mapped to the problem before Huma reads the body). The YAML import's 5 MB limit ([SPEC-yaml-as-code-03]) will override it on its own route later.
- `api/openapi.yaml` regenerated to document the `503` and `413` problems; `make openapi-check` passes.

**arch-web**
- A `401` from the API triggers at most one automatic sign-in per 60 s, tracked in `sessionStorage` as a timestamp only. A second `401` inside that window shows "Your session was rejected by the API. Try signing in again." with the buttons "Sign in again" and "Sign out", instead of redirecting.
- A `503 /problems/auth-unavailable` from the API (today it would land in the shell's "Couldn't load your profile") shows the existing "Sign-in is unavailable, try again" state with its "Try again" button. The web client needs to read the problem `type` from the body, since `ApiError` carries only the status today.
- `src/api/schema.d.ts` regenerated from the merged `api/openapi.yaml`.

**Not in this job:** `arch-deploy` (its realm export, when it arrives, must carry the `client_id` mapper on every `arch-ci-*` client); CSP, security headers and ingress rules; trace sampling; `.github/*` changes; any model or write endpoint. The hub's `dev/keycloak/arch-realm.json` already has the mapper on `arch-ci-platform`, so the live check only needs a Keycloak re-import (without dropping the shared dev data).

## Why
Every item is visible in the current code: `internal/auth/jwks.go` locks `mu` for the whole of `get()` including `fetch()` and only applies the 30 s limit after `loaded` is true; `internal/auth/principal.go` treats `client_id != ""` or a `service-account-` username as a service account; `internal/httpapi/serve.go` builds both servers with only `ReadHeaderTimeout`; and `src/api/client.ts` calls `onUnauthorized` on every `401`, which `AuthProvider.reauthenticate` turns into `removeUser` and `RequireAuth` into a new `signinRedirect`. The spec already states the target behaviour, the decisions are made, and the work stays inside two packages of `arch-api` and the auth/API layer of `arch-web`, so it fits one PR per repo. It is high risk because it touches token validation and the access middleware, which the Factory notes list under High risk and Always escalate.

## Questions
None.

## Research
None.

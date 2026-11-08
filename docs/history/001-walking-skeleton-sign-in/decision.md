ESCALATE

## Summary
- Round 1 built the walking skeleton in both empty repos. arch-api (CliXiD/arch-api#2) now has Go/gin/Huma, JWT validation, default-deny roles, `GET /api/v1/me`, `/healthz`, `/readyz`, `/metrics`, goose with a no-op baseline migration, and CI. arch-web (CliXiD/arch-web#2) now has a React SPA with OIDC PKCE sign-in, in-memory tokens, an app shell and user menu, and CI.
- The gate passed for both repos, and all six reviews (code, contract, db, security, ui, ux) are `VERDICT: PASS` with no findings. The Notes are hardening items, not defects.
- The change stays inside intake's Scope and REPOS (arch-deploy is untouched) and follows the spec's Contract and merge order.
- The job has to escalate by its nature. It creates the auth middleware and role mapping, two new unauthenticated endpoints (`/healthz`, `/readyz`) plus `/metrics` on its own port, the first migration, two CI workflows and new dependencies. All of these are on the Always escalate list or the general escalation list. Intake and the spec both expected this.

## Why
The build looks correct and complete against the spec. My spot checks agree with build.md and the reviews: the access middleware is default-deny, the httpapi role and registry tests pass, tokens use an in-memory store, and the committed `schema.d.ts` regenerates from arch-api's `openapi.yaml` with no differences. Factory notes require a human for auth middleware, role mapping, new unauthenticated endpoints, migrations, CI config and new dependencies. One criterion (17, the real-browser sign-in) also still needs a human to run it.

## Acceptance criteria
1. [arch-api] Token validation table tests: met. build.md lists every subtest, including unknown `kid` (fetch count 1 to 2) and the 30 s rate limit. The gate's `go test` passed.
2. [arch-api] Role tests (admin gets every role; no arch role gets 403 `/problems/forbidden`): met. I re-ran `TestMe`, `TestProblems` and `TestRegistry*` in `internal/httpapi` and they pass.
3. [arch-api] Registry test fails on an undeclared role: met. build.md describes the temporary route that made it fail. `TestRegistryCheckCatchesUndeclaredOperations` keeps it covered, and I read the middleware: an undeclared role or misused `public` gets 403.
4. [arch-api] Live `/api/v1/me` returns 401 without a token, the editor gets teams `platform`, and the client-credentials token gets `actor_kind: service`: met. Builder ran it against the real Keycloak (on port 5130 instead of 8080).
5. [arch-api] `/readyz` returns 503 `migrations` before `migrate up` and 200 after, and `/healthz` stays 200: met. It ran on a scratch DB. The "database" case was tested with a closed port instead of stopping Postgres.
6. [arch-api] `/metrics` is served on the metrics port and returns 404 on the API port: met (live).
7. [arch-api] Missing `OIDC_ISSUER` prints a message naming it and exits non-zero: met (live and `TestRun`).
8. [arch-api] The request log contains no `Authorization` value: met (`TestRequestLogNeverContainsTheToken` and live logs).
9. [arch-api] `make openapi` and `make openapi-check`: met. The stale-file check exited non-zero and only `api/openapi.yaml` was modified. The output is deterministic.
10. [arch-api] golangci-lint is pinned as a tool directive (v2.15.0): met.
11. [arch-api] The hub check script passes: met (round-1 `checks.md` says GATE: PASS).
12. [arch-api] CI workflow: met (new `.github/workflows/ci.yml`).
13. [arch-api] `.env.example` and README: met.
14. [arch-web] Vitest tests for signing in, unavailable sign-in, the user menu and the 403 page: met (24 tests pass in the gate).
15. [arch-web] Tokens stay in memory only: met. The test uses the real `UserManager` settings, and I confirmed `userStore` is an `InMemoryWebStorage`.
16. [arch-web] A silent-renew failure re-signs in, and Sign out works: met (tests).
17. [arch-web] Manual browser sign-in as `editor` with `pnpm dev` on 5173: **not met**, never run. The builder had no browser available, and the realm accepts only port 5173. The API side of the same login was verified live in criterion 4.
18. [arch-web] `schema.d.ts` is generated from arch-api's `openapi.yaml`: met. I regenerated it myself from the sibling worktree and it matches except for the header (the cross-repo check).
19. [arch-web] The hub check script passes: met (GATE: PASS).
20. [arch-web] CI workflow: met.
21. [arch-web] `.nvmrc` is 26, engines `>=26`, no `public/config.json`: met.

## Merge order
1. CliXiD/arch-api#2 (merge first).
2. CliXiD/arch-web#2 (after arch-api. If arch-api changes in review, run `pnpm gen:api` again before merging).
Nothing is deployed in this slice.

## Docs impact
- `docs/specs/001_identity-access.md`:
  - [SPEC-identity-access-08] and Interfaces: change the path to `GET /api/v1/me`.
  - Interfaces: replace the web config names `OIDC_AUTHORITY`/`OIDC_CLIENT_ID`/`API_BASE_URL` with the `/config.json` keys `apiBaseUrl`/`oidcAuthority`/`oidcClientId`, plus the `VITE_*` fallback.
  - Note that a service account's `subject` is its client id.
- `docs/specs/009_operations.md`:
  - Interfaces: add `OIDC_JWKS_URL` (optional) and the defaults for `HTTP_ADDR`, `METRICS_ADDR` and `LOG_LEVEL`.
  - [SPEC-operations-01]: give the `/readyz` body as `{"status","failing":["database"|"migrations"]}`.
  - [SPEC-operations-02]: list the metric names `http_requests_total`, `http_request_duration_seconds`, and `db_pool_acquired_connections`/`idle`/`total`/`max`.
- No new ADR is needed. React Router runs in library mode (`createBrowserRouter`), which I read as consistent with [ADR-0007].

## For the human
This job builds the security base for every later slice, so the Factory notes require your review before merging. Please decide or check the following:

1. **Auth middleware and role mapping.** Approve `arch-api/internal/httpapi/api.go` (`accessMiddleware`, `register()`), `internal/auth/verifier.go`, `internal/auth/jwks.go` and `internal/auth/principal.go` in CliXiD/arch-api#2. Specifically:
   - Service-account detection: a `client_id` claim or a `service-account-` username prefix, with the client id becoming the subject. Security Note 2 suggests a stricter rule before change_log actor writes arrive.
   - The JWKS fetch runs while the cache mutex is held, and the initial load is not rate-limited while Keycloak is down (code and security Notes 1). Decide whether to fix this now or in a follow-up issue.
2. **Unauthenticated endpoints.** Confirm `/healthz` and `/readyz` on the API port and `/metrics` on `METRICS_ADDR`. They are public by design. Later, arch-deploy must not expose `/readyz` or `/metrics` on a public ingress.
3. **Migration.** `migrations/00001_baseline.sql` is a new no-op (`SELECT 1`) file. It is the first file in this protected path.
4. **CI and dependencies.** Review the new `.github/workflows/ci.yml` in both repos (`contents: read`, actions pinned to major tags rather than SHAs) and the new dependency set (`go.mod`/`go.sum`, `package.json`/`pnpm-lock.yaml`). TypeScript is pinned to 5.9 because of peer ranges.
5. **Manual check (criterion 17, not done).** Run `dev/bin/stack up`, start arch-api, then run `pnpm dev` in arch-web on port 5173. Open `http://localhost:5173/some/route` and sign in as `editor`/`password`. Confirm you return to `/some/route` and see "Editor Local", "Roles: viewer, editor" and "Teams: platform", that `/api/v1/me` carries `Authorization` and `traceparent`, and that "Sign out" ends on Keycloak's sign-in page.
6. **UI copy chosen by the spec** ("Loading…", "Couldn't load your profile", "Teams: none", "Architecture E2E is not configured: missing …"). Accept it or change it.

Then merge CliXiD/arch-api#2 first and CliXiD/arch-web#2 after it, and update the docs listed under Docs impact.

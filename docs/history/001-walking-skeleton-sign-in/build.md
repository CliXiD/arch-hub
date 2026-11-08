STATUS: READY

# Build: Walking skeleton: sign-in, /api/v1/me and health

## Summary
- `arch-api` is now a Go 1.27 module (gin + Huma v2). It has `serve` and `migrate up|status`, env config, `/healthz`, `/readyz`, `/metrics` on its own port, JSON request logs, optional OTLP tracing, JWT validation with default-deny minimum roles, and `GET /api/v1/me`.
- `arch-web` is now a Vite + React 19 SPA. It loads runtime config, signs in with Keycloak (Authorization Code + PKCE), keeps tokens in memory, renews them silently, shows an app shell whose user menu comes from `/api/v1/me`, and signs out RP-initiated.
- `api/openapi.yaml` is generated (`make openapi`), and `make openapi-check` catches a stale copy. `arch-web/src/api/schema.d.ts` is generated from this branch's `openapi.yaml`.
- Both repos have a CI workflow (new `.github/workflows/ci.yml`) running the same steps as the gate. Both gate scripts exit 0.
- Draft PRs: CliXiD/arch-api#2 and CliXiD/arch-web#2. They link to each other and to CliXiD/arch-hub#3.

## Changes

### arch-api
- `go.mod`, `go.sum`: module `github.com/CliXiD/arch-api`, `go 1.27`, `toolchain go1.27.2`, plus a `tool github.com/golangci/golangci-lint/v2/cmd/golangci-lint` directive (v2.15.0).
- `.golangci.yml`: v2 format. The `standard` linters plus `bodyclose`, `errcheck`, `gosec`, `revive`, with the gofmt and goimports formatters.
- `.env.example`: every variable in the Contract env table, with the `dev/env/arch-api.env` values. `OIDC_JWKS_URL` and `OTEL_EXPORTER_OTLP_ENDPOINT` are commented out.
- `cmd/arch-api/main.go`: subcommand dispatch only. It loads config, then calls `httpapi.Serve` or `db.Migrate`. Anything else prints usage and exits 2. `main_test.go` covers usage and config errors.
- `cmd/openapi/main.go`: prints the OpenAPI YAML from the same `httpapi.NewAPI` registration, without a database or Keycloak. Top-level keys come first in a fixed order, so the file starts with `openapi: 3.1.0` and is the same on every run.
- `internal/config`: `LoadServe` and `LoadMigrate`. One error names every missing or invalid variable (`config: X is required, Y is invalid`) and never prints a value. It validates `LOG_LEVEL`, the OTLP protocol and endpoint, the OIDC URLs and the DB URLs.
- `internal/auth`:
  - `principal.go`: `Role`, `Principal`, `EffectiveRoles` (admin ⊃ editor ⊃ viewer, always in the order viewer, editor, admin), `PrincipalFromClaims` (service accounts from `client_id` or a `service-account-` username; the client id comes from `client_id`, else `azp`), and the context helpers.
  - `jwks.go`: in-memory key cache with lazy discovery. An unknown `kid` triggers one refetch, then at most one per 30 s (on the injectable clock). Fetch errors are logged without the token.
  - `verifier.go`: golang-jwt/v5. It accepts RS256/384/512, PS256, ES256 and ES384, and the alg must match the JWK. It checks `iss`, `aud` (string or array), a required `exp`, and `nbf` with 30 s leeway. Every failure is `ErrUnauthenticated`.
  - `authtest/`: a fake realm (discovery and JWKS with a fetch counter) and a token signer, used by tests only.
- `internal/db`: `NewPool` (pgxpool, no connect at start-up, `otelpgx` tracer only when tracing is on, without query arguments). `VersionReader` (a plain `SELECT max(version_id) FROM goose_db_version`). `LatestVersion` (from the embedded file names). `Migrate` (goose v3 Provider, postgres dialect, `up` and `status`).
- `internal/health`: `Checker` runs a ping, then the migrations check only after the ping succeeds, within 2 s. `Report.HTTPStatus()` gives 200 or 503.
- `internal/observability`:
  - slog JSON logger.
  - Request logger: `method`, `route` (the template, or `unmatched`), `status`, `duration_ms`, `trace_id`, `actor`. No headers, query strings or bodies.
  - Prometheus: `http_requests_total`, `http_request_duration_seconds`, the `db_pool_*` gauges (a custom collector over `pool.Stat()`), and the Go and process collectors.
  - OTLP setup over grpc or http/protobuf, with `service.name=arch-api` and the W3C TraceContext propagator.
- `internal/httpapi`:
  - `api.go`: Huma config with the OpenAPI, docs and schemas paths empty and `CreateHooks` cleared (no `$schema` field or `Link` header), and the `bearer` http/JWT scheme. Every operation goes through `register()`. It sets `Metadata["minRole"]`, and on `/api/v1` operations it adds the bearer `Security` and documents 401 and 403.
  - Huma middleware `accessMiddleware`: 401 without a valid token. 403 when the role is too low, when an operation declares no role, or when `public` is used on a path other than `/healthz` or `/readyz`. RFC 9457 `application/problem+json`. It puts the `Principal` in the request context and the subject on the gin context for the log.
  - `routes.go`: `/healthz`, `/readyz` (503 documented) and `/api/v1/me`. The `Me` slices are non-nullable and `teams` is never null.
  - `engine.go`: middleware order is recovery (logs no request data), otelgin (when tracing is on), metrics, request log, then CORS (only when `CORS_ORIGINS` is set; mounted before auth so preflights are answered), then Huma.
  - `serve.go`: wires everything. Two `http.Server`s: the API, and `/metrics` on `METRICS_ADDR` only. Graceful shutdown on SIGINT/SIGTERM.
- `migrations/embed.go` (new, `//go:embed *.sql`) and `migrations/00001_baseline.sql` (new, `SELECT 1` up and down, no schema objects). No existing file under `migrations/` or `.github/` was touched.
- `Makefile`: `make openapi` and `make openapi-check`. The check writes to a `mktemp` file, diffs, removes the temp file and fails on any difference.
- `api/openapi.yaml`: generated, OpenAPI 3.1.0.
- `.github/workflows/ci.yml` (new): runs on `pull_request` and on push to `main`. `setup-go` with `go-version-file: go.mod`, then vet, golangci-lint, test, build and openapi-check.
- `README.md`: what the service is, prerequisites, how to run it, the env table, endpoints, OpenAPI, checks, layout, and the hub docs.
- Tests: `internal/{auth,config,db,health,httpapi,observability}` and `cmd/arch-api`, all table-driven with testify, no network or DB.

### arch-web
- `package.json`, `pnpm-lock.yaml`, `.nvmrc` (`26`):
  - `packageManager: pnpm@10.34.9` and `engines.node: >=26`.
  - Scripts: `dev`, `build`, `lint`, `typecheck` (`tsc --noEmit`), `test` (`vitest run`) and `gen:api`.
  - Deps: React 19.3, React Router 7.18, TanStack Query 5, oidc-client-ts 3.5, openapi-fetch 0.17.
  - Dev deps: Vite 8, Tailwind 4 via `@tailwindcss/vite`, ESLint 10 with typescript-eslint and react-hooks, Vitest 5 with jsdom and Testing Library, openapi-typescript 7.
  - TypeScript is pinned to 5.9: TS 7 is outside the peer ranges of typescript-eslint (`<6.1`) and openapi-typescript (`^5`).
- `vite.config.ts`, `tsconfig.json` (strict), `eslint.config.js` (flat config; ignores `dist/` and `src/api/schema.d.ts`), `index.html`, `src/index.css`, `src/vite-env.d.ts`, `src/test/setup.ts`.
- `.env.example`: the three `VITE_*` values from `dev/env/arch-web.env`. There is no `public/config.json`.
- `src/config.ts`: fetches `/config.json` and falls back key by key to `VITE_*` when the response isn't ok, isn't JSON (Vite's HTML), fails, or lacks a key. Otherwise it returns the missing keys.
- `src/api/schema.d.ts`: generated with `pnpm gen:api` from `../arch-api/api/openapi.yaml`.
- `src/api/client.ts`: openapi-fetch client. Its middleware adds `Authorization: Bearer` from the in-memory user and a fresh `traceparent` (`crypto.getRandomValues`), and calls `onUnauthorized` on a 401.
- `src/api/ApiProvider.tsx`: provides the client. `src/api/me.ts`: the `useMe()` query and `ApiError`.
- `src/auth/userManager.ts`: `userManagerSettings` with code + PKCE, `openid profile email`, `${origin}/auth/callback` and `${origin}/`, `automaticSilentRenew`, and `userStore` as an in-memory `WebStorageStateStore`. Also `createUserManager` and the `AuthClient` type (the subset of UserManager the app uses).
- `src/auth/context.ts` and `src/auth/AuthProvider.tsx`: the `useAuth()` context.
  - Sign-in carries `returnTo` through the redirect. Callback completion returns `returnTo`.
  - `reauthenticate` (on `addSilentRenewError` or a 401) removes the user, and the guard then signs in again with the current route.
  - Sign out calls `removeUser()`, then `signoutRedirect({ id_token_hint })`.
- `src/auth/RequireAuth.tsx`: the guard. It shows "Signing in…" (`role="status"`) and calls `signinRedirect` with `pathname + search + hash`. On failure it shows "Sign-in is unavailable, try again" with a "Try again" button that retries.
- `src/routes/AuthCallback.tsx`: calls `signinRedirectCallback()`, then `navigate(returnTo ?? "/", { replace: true })`. An error shows the unavailable state.
- `src/App.tsx`, `src/main.tsx`:
  - `createBrowserRouter`: `/auth/callback`, then `*` → the guard → the shell.
  - Providers: auth, API, query.
  - "Architecture E2E is not configured: missing …" when config is incomplete.
- `src/components/Shell.tsx`, `UserMenu.tsx`, `StatusMessage.tsx`:
  - Header with an `<h1>` "Architecture E2E" and the user menu. `<main>` says "The landscape is coming soon."
  - The menu button is labelled with `me.name` and has `aria-expanded` and `aria-controls`. Its panel shows "Roles: …", "Teams: …" (or "Teams: none") and "Sign out". Escape closes it and returns focus to the button.
  - States: "Loading…" status, the 403 full-page no-access message with "Sign out", and "Couldn't load your profile" with "Try again". Tailwind classes only.
- `.github/workflows/ci.yml` (new): runs on `pull_request` and on push to `main`. `pnpm/action-setup`, then `setup-node` with `.nvmrc` and the pnpm cache, then install --frozen-lockfile, lint, typecheck, test, and build with the three `VITE_*` values.
- `README.md`: prerequisites, how to run it, `/config.json` and the `VITE_*` fallback, `gen:api` and `ARCH_API_OPENAPI`, checks, and the hub docs.
- Tests: `src/App.test.tsx`, `src/config.test.ts`, `src/api/client.test.ts`, `src/auth/userManager.test.ts`, `src/NotConfigured.test.tsx`, with the fake client in `src/test/fakeAuth.ts`.

## Acceptance criteria
1. [x] [arch-api] Token validation tests: `go test -count=1 -v ./internal/auth/...` passes with these subtests:
   - `valid` and `no_token`
   - `non-Bearer_scheme` and `malformed`
   - `alg_none` and `alg_HS256`
   - `bad_signature` and `wrong_issuer`
   - `wrong_audience_string` and `wrong_audience_array`
   - `expired_31_s_rejected` and `expired_29_s_accepted`
   - the nbf ±31/29 s cases
   - `unknown_kid_one_refetch_then_accepted` (fetch count 1 → 2)
   - `second_unknown_kid_within_30_s_no_refetch` (stays at 2, then 3 after 30 s)
2. [x] [arch-api] Role tests:
   - `TestMe/admin_gets_every_role`: `/api/v1/me` returns `["viewer","editor","admin"]`.
   - `TestProblems/no_arch_role`: 403, `type: /problems/forbidden`, `detail: requires role viewer`.
   - `TestEffectiveRoles` and `TestPrincipalFromClaims` cover the editor with group, and the service token (`actor_kind: service`, `subject: arch-ci-platform`).
3. [x] [arch-api] I added a temporary `huma.Register` for `/api/v1/temp` without a role. `go test ./internal/httpapi/...` then failed with `GET /api/v1/temp (get-temp): no minimum role declared` (plus missing bearer and 401/403). Reverted; it passes again. `TestRegistryCheckCatchesUndeclaredOperations` and `TestUndeclaredOperationIsForbiddenAtRuntime` keep this proven.
4. [x] [arch-api] Against the running local stack. I used the binary on `:5130` (my port) instead of `:8080`, with the env from `apply-env --to <worktree> arch-api`.
   - No token: `401`, `Content-Type: application/problem+json`, `"type":"/problems/unauthenticated"`.
   - The `editor` token came from a scripted Auth Code + PKCE login, because the realm has no direct grants. Response: `200` with `"roles":["viewer","editor"]`, `"teams":["platform"]`, `"name":"Editor Local"`.
   - `admin` gives all three roles; `viewer` gives `teams: []`.
   - The client-credentials token from `arch-ci-platform`/`dev-ci-secret` gives `200` with `"actor_kind":"service"`, `"subject":"arch-ci-platform"`.
   - A tampered token gives 401.
5. [x] [arch-api] On a fresh scratch database (`arch_job001_scratch`, created and then dropped), instead of `stack reset`, which would drop the shared dev data:
   - With `serve` running before migrate: `/readyz` gave `503 {"status":"unavailable","failing":["migrations"]}`.
   - `migrate status` showed `pending 1`. `migrate up` applied 00001. Then `/readyz` gave `200 {"status":"ok"}`.
   - `/healthz` gave `200 {"status":"ok"}` both times.
   - I didn't stop the shared Postgres. With `DATABASE_URL` pointing at a closed port (5499), `/readyz` gave `503 {"status":"unavailable","failing":["database"]}` and `/healthz` stayed 200.
6. [x] [arch-api] `curl :5131/metrics` (`METRICS_ADDR`) lists `http_requests_total{method="GET",route="/api/v1/me",status="200"}`, `route="unmatched"`, `db_pool_total_connections 1` and `db_pool_max_connections 10`. `curl -i :5130/metrics` gives `404`.
7. [x] [arch-api] `env -u OIDC_ISSUER ./bin/arch-api serve` printed `config: OIDC_ISSUER is required` and exited 1. `TestRun/serve_without_OIDC_ISSUER` covers the same.
8. [x] [arch-api] `TestRequestLogNeverContainsTheToken` sends `Authorization: Bearer <jwt>` and a query string through the full engine into a buffer.
   - It asserts `msg`, `method`, `route`, `status`, `duration_ms`, `trace_id` (empty) and `actor` (the subject).
   - It asserts the line has no token, `Authorization`, `Bearer`, query value or email.
   - Live, the stack's log lines had no `Bearer` or `eyJ`. With `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`, an incoming `traceparent` showed up as `trace_id` in the log. Jaeger received the trace for service `arch-api` with spans `GET /readyz`, `pool.acquire`, `connect` and `SELECT`.
9. [x] [arch-api] OpenAPI:
   - `make openapi` then `git status --porcelain` is empty.
   - After `echo '# stale' >> api/openapi.yaml`, `make openapi-check` exited 2 and the status showed only ` M api/openapi.yaml`. Restored with `git checkout`.
   - The file starts with `openapi: 3.1.0`. It contains `/api/v1/me`, `/healthz`, `/readyz` and `securitySchemes.bearer` (http/bearer/JWT), and no `/docs` or `/openapi` path.
   - Three runs gave the same sha.
10. [x] [arch-api] `go.mod` has `go 1.27`, `toolchain go1.27.2` and `tool github.com/golangci/golangci-lint/v2/cmd/golangci-lint`. `go tool golangci-lint version` prints `2.15.0 built with go1.27.2`.
11. [x] [arch-api] The gate script `factory/checks/arch-api.sh` exited `0` in the worktree.
12. [x] [arch-api] `.github/workflows/ci.yml` runs on `pull_request` (and on push to `main`). Its steps are `go vet ./...`, `go tool golangci-lint run ./...`, `go test -count=1 ./...`, `go build ./...` and `make openapi-check`.
13. [x] [arch-api] `.env.example` has all 11 Contract variables. `README.md` documents the commands, env table, endpoints, `make openapi`/`openapi-check` and the checks.
14. [x] [arch-web] `pnpm run test` gives 24 passed in 5 files. In `App.test.tsx`:
    - "shows Signing in… while redirecting, with the current route as returnTo"
    - "shows Sign-in is unavailable when discovery fails, and Try again retries"
    - "shows the user menu with name, roles and teams after /me"
    - "replaces the page with the no-access message on 403"
    - plus the callback, loading, error and Teams: none cases
15. [x] [arch-web] `pnpm vitest run -t "memory"`: 1 passed. The test is "keeps tokens in memory only: nothing in localStorage, no token in sessionStorage". It uses the real `userManagerSettings` and `UserManager`, with discovery and the token endpoint stubbed. It checks PKCE S256, then completes `signinRedirectCallback`, then asserts `localStorage.length === 0` and that no sessionStorage key or value contains the access, refresh or ID token.
16. [x] [arch-web] "signs in again with the current route when the silent renew fails": `removeUser` is called, then `signinRedirect({ state: { returnTo: "/some/route?view=list" } })`. "Sign out calls signoutRedirect with the id token and removes the user" covers sign-out. A 401 test covers the same re-sign-in path.
17. [ ] [arch-web] Not verified in a real browser.
    - Neither `agent-browser` nor Playwright browsers are installed.
    - The realm's `arch-web` client only accepts `http://localhost:5173/*`, so sign-in can't complete on my port 5131.
    - What I did check: `vite --port 5131` serves the app for `/some/route`, `/config.json` returns `text/html` (so the `VITE_*` fallback applies), and the env is injected.
    - The behaviour is covered by the component tests in 14–16, the client test in Validation, and the real Keycloak Auth Code + PKCE login against the API in 4.
    - A human should run the manual check with `pnpm dev` on 5173.
18. [x] [arch-web] After committing, `pnpm gen:api` then `git status --porcelain src/api/schema.d.ts` is empty. The file starts with `/** This file was auto-generated by openapi-typescript.`
19. [x] [arch-web] The gate script `factory/checks/arch-web.sh` exited `0`: Node 26 via nvm, frozen install, lint, typecheck, 24 tests, then `.env` from the hub and a build.
20. [x] [arch-web] `.github/workflows/ci.yml` runs on `pull_request` (and on push to `main`). `setup-node` uses `node-version-file: .nvmrc`. The steps are `pnpm run lint`, `typecheck`, `test` and `build`.
21. [x] [arch-web] `.nvmrc` is `26`, `engines.node` is `>=26`, and there is no `public/` folder (so no `public/config.json`).

## Validation
- arch-api (`GOTOOLCHAIN=go1.27.2`):
  - `go vet ./...` passed.
  - `go tool golangci-lint run ./...` passed (0 issues).
  - `go test -count=1 ./...` passed (7 packages with tests).
  - `go build ./...` passed.
  - `make openapi-check` passed.
  - The gate (`FACTORY_HUB=… FACTORY_REPO_KEY=arch-api FACTORY_BASE=main bash factory/checks/arch-api.sh`) exited 0.
  - The live stack checks in criteria 4–8 passed.
- arch-web (Node 26.13.0, pnpm 10.34.9):
  - `pnpm run lint` passed.
  - `pnpm run typecheck` passed.
  - `pnpm run test` passed (24).
  - `pnpm run build` passed.
  - The gate (`factory/checks/arch-web.sh`) exited 0.
  - `pnpm gen:api` left no diff.

## Log
### Round 1
- Built both repos from empty, following spec.md. Worked in merge order: arch-api first, then arch-web generated from its `openapi.yaml`. Both worktrees were on `factory/001-walking-skeleton-sign-in`.
- Environment setup:
  - Go 1.27.2 is downloaded through `GOTOOLCHAIN`.
  - Installed Node 26.13.0 with nvm. Installed pnpm 10.34.9 globally for that Node, because Node 26 ships no corepack and the gate needs `pnpm`.
- Decisions inside the spec's latitude:
  - Huma's `YAML()` sorts keys, so `cmd/openapi` reorders the top-level keys to start with `openapi`.
  - The `Me` and `/readyz` slices are `nullable:"false"`, so the generated TS types aren't `| null`.
  - `register()` also documents 401/403 on `/api/v1`. The middleware refuses `public` outside `/healthz` and `/readyz` at runtime as well.
  - The DB URLs are validated in config, so a bad URL prints `config: DATABASE_URL is invalid` without the value.
  - Tokens without `exp` are rejected.
  - The JWKS initial load isn't rate-limited; only unknown-`kid` refetches are.
  - TypeScript is pinned to 5.9 because of peer ranges.
  - Sign-out removes the user before `signoutRedirect`, because the redirect never resolves. A `signingOut` flag stops the guard from starting a new sign-in meanwhile.
- Stack side effects: I created and dropped a scratch database `arch_job001_scratch` in the shared Postgres. No `stack reset` and no Postgres stop.
- Worktree side effects: `apply-env` wrote `.env` in the arch-api worktree, and the gate's `hub_env` wrote it in arch-web. Both are gitignored, as are `bin/` in arch-api and `node_modules/` and `dist/` in arch-web.
- Leftover file: an early scratch file at `/tmp/o1.yaml` (a copy of the generated OpenAPI) was left, because the removal command was blocked; it is harmless.
- Opened the draft PRs CliXiD/arch-api#2 and CliXiD/arch-web#2, and cross-linked them under Related PRs.

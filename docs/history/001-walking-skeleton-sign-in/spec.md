# Walking skeleton: sign-in, /api/v1/me and health

> Issue #3: Walking skeleton: sign-in, /api/v1/me and health

## Summary
- First code in both app repos: `arch-api` becomes a Go 1.27 module (gin + Huma v2) with `serve` and `migrate up|status`, env config, JSON request logs, `/healthz`, `/readyz`, `/metrics` on its own port, optional OTLP tracing, JWT auth with default-deny roles, and `GET /api/v1/me`.
- `arch-web` becomes a Vite + React 19 SPA. It loads runtime config, signs in with Keycloak (Authorization Code + PKCE), keeps tokens in memory, refreshes them silently, shows an app shell whose user menu comes from `/api/v1/me`, and signs out RP-initiated.
- The issue's Decisions, Contract and Acceptance criteria carry over unchanged. Intake added `MIGRATE_DATABASE_URL` ([SPEC-operations] Interfaces, [ADR-0014]).
- Both repos get the exact commands the hub gate already runs (`factory/checks/arch-api.sh`, `factory/checks/arch-web.sh`) and a GitHub Actions workflow running the same steps ([ADR-0010]).
- Risk is high: this creates token validation, role mapping, three public endpoints, the first migration and CI files under protected paths (`.github/*`, `migrations/*`). Every file here is new; no existing file under a protected path is edited.

## Context

**Both repos are empty.** Each has only `README.md` and `.gitignore` (`arch-api:.gitignore` covers `.env`, `/bin/`, `/dist/`, `*.test`, `coverage.*`; `arch-web:.gitignore` covers `.env`, `node_modules/`, `dist/`, `coverage/`, `playwright-report/`). There is no code pattern in the repos to reuse yet. The patterns to follow come from the hub:

- **Documents (source of truth):** `docs/specs/001_identity-access.md` ([SPEC-identity-access-01]..[09]), `docs/specs/009_operations.md` ([SPEC-operations-01]..[05]), [ADR-0003] (gin + Huma v2, `make openapi`, RFC 9457, pinned golangci-lint), [ADR-0004] (pgx/v5, goose SQL migrations in `arch-api/migrations/`), [ADR-0007] (React 19, Vite, TS, Tailwind 4, React Router 7, TanStack Query, `oidc-client-ts`, `openapi-typescript` + `openapi-fetch`, Vitest + Testing Library, pnpm), [ADR-0008] (Keycloak, realm roles, `teams` claim), [ADR-0010] (CI steps), [ADR-0011] (slog JSON, health, Prometheus, OTLP, `traceparent`), [ADR-0013] (Go 1.27 / `toolchain go1.27.x`; Node 26 in `.nvmrc`, `engines.node: ">=26"`), [ADR-0014] (`MIGRATE_DATABASE_URL` for `migrate`, `DATABASE_URL` for the server).
- **Gate:** `factory/checks/arch-api.sh` runs, with `GOTOOLCHAIN=auto` and `GOFLAGS=-mod=readonly`: `go vet ./...`, `go tool golangci-lint run ./...`, `go test -count=1 ./...`, `go build ./...`, `make openapi-check`. `factory/checks/arch-web.sh` selects Node from `.nvmrc`, runs `pnpm install --frozen-lockfile` when `pnpm-lock.yaml` exists, then `pnpm run lint`, `pnpm run typecheck`, `pnpm run test`, copies `dev/env/arch-web.env` to `.env`, and runs `pnpm run build`.
- **Dev stack:** `dev/arch-api/start.sh` runs `go run ./cmd/arch-api migrate up` then `go run ./cmd/arch-api serve`, so the main package must be `cmd/arch-api`. `dev/arch-web/start.sh` runs `pnpm install --frozen-lockfile` then `pnpm dev --host 0.0.0.0 --port 5173 --strictPort`.
- **Env files:** `dev/env/arch-api.env` sets `DATABASE_URL`, `MIGRATE_DATABASE_URL`, `HTTP_ADDR=:8080`, `METRICS_ADDR=:9090`, `CORS_ORIGINS=http://localhost:5173`, `LOG_LEVEL=debug`, `OIDC_ISSUER=http://localhost:8180/realms/arch`, `OIDC_AUDIENCE=arch-api`, `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, and leaves `OTEL_EXPORTER_OTLP_ENDPOINT` commented out. `dev/env/arch-web.env` sets `VITE_API_BASE_URL=http://localhost:8080` (an origin with no path), `VITE_OIDC_AUTHORITY=http://localhost:8180/realms/arch` and `VITE_OIDC_CLIENT_ID=arch-web`.
- **Realm** (`dev/keycloak/arch-realm.json`):
  - Access tokens live 300 s. Realm roles arrive in `realm_access.roles`, mixed with non-arch roles such as `default-roles-arch` and `offline_access`. `viewer` comes from the default role.
  - The group mapper gives `teams: ["platform"]` without the path. The client `arch-ci-platform` sets `teams: ["platform"]` as a hardcoded claim and its service account has `editor`. Every client has an `arch-api` audience mapper.
  - The public client `arch-web` uses PKCE S256. Its redirect and post-logout URIs are `http://localhost:5173/*`.
  - The service-account user is `service-account-arch-ci-platform`.
- **Postgres:** `dev/postgres/init/02-arch-app.sql` creates the runtime role `arch_app` without table grants. For now the dev stack keeps `DATABASE_URL` on the owner `arch` ([ADR-0014] Consequences).

## Contract

The interface between `arch-api` and `arch-web`. `arch-api/api/openapi.yaml` is generated from it ([ADR-0003]) and `arch-web/src/api/schema.d.ts` is generated from that file ([ADR-0007]).

### HTTP (arch-api, `HTTP_ADDR`, default `:8080`)

| method | path | auth | success | errors |
|---|---|---|---|---|
| GET | `/healthz` | public | `200 {"status":"ok"}` | — |
| GET | `/readyz` | public | `200 {"status":"ok"}` | `503 {"status":"unavailable","failing":["database"]}` or `{"status":"unavailable","failing":["migrations"]}` |
| GET | `/api/v1/me` | bearer, min role `viewer` | `200 Me` | `401`, `403` problems |

```ts
type Me = {
  subject: string;          // token `sub`; for a service account, its client id ([SPEC-identity-access-07])
  name: string;             // `name`, else `preferred_username`; for a service account, its client id
  email: string;            // `email` claim, "" when absent
  roles: ("viewer" | "editor" | "admin")[]; // effective set, always in this order, e.g. admin => ["viewer","editor","admin"]
  teams: string[];          // `teams` claim, [] when absent (never null)
  actor_kind: "user" | "service";
};
```

`/readyz` lists `failing: ["database"]` when the ping fails; the migrations check runs only when the ping succeeds. Both responses are `application/json`. Responses carry no `$schema` field and no `Link` describedby header.

**Errors** on every `/api/v1` route, as RFC 9457 `application/problem+json`:

```json
{ "type": "/problems/unauthenticated", "title": "Unauthorized", "status": 401, "detail": "a valid bearer token is required" }
{ "type": "/problems/forbidden", "title": "Forbidden", "status": 403, "detail": "requires role viewer" }
```

- `401` is returned when the token is missing, not `Bearer`, malformed, signed with `alg` `none` or an HMAC alg, has a bad signature or an unknown `kid` (even after the one refetch), has the wrong `iss`, has an `aud` (string or array) that doesn't contain `OIDC_AUDIENCE`, or has expired (`exp`) or isn't yet valid (`nbf`) by more than 30 s.
- `403` is returned when none of `viewer`, `editor` or `admin` is in `realm_access.roles`, or the effective roles are below the route's minimum.
- `detail` never contains the token, a claim value or a header value.

**OpenAPI:**
- The document declares an `http`/`bearer` (JWT) security scheme. Every `/api/v1` operation references that scheme and documents `401` and `403` with the problem schema.
- `/healthz` and `/readyz` have no security.
- Huma's built-in `/openapi*`, `/docs` and `/schemas` routes are not served. No other unauthenticated route exists.

**CORS:**
- Origins in `CORS_ORIGINS` (comma-separated) may call every route. Allowed methods are `GET, POST, PUT, PATCH, DELETE, OPTIONS`; allowed headers are `Authorization, Content-Type, traceparent`.
- Preflight `OPTIONS` is answered before authentication.
- With `CORS_ORIGINS` empty, no CORS headers are sent.

### Metrics (arch-api, `METRICS_ADDR`, default `:9090`)
- `GET /metrics` (public, Prometheus text). It is not served on `HTTP_ADDR`, where it returns `404`.
- It exposes `http_requests_total{method,route,status}`, `http_request_duration_seconds{method,route,status}` (histogram), and the pgxpool gauges `db_pool_acquired_connections`, `db_pool_idle_connections`, `db_pool_total_connections` and `db_pool_max_connections`, plus the default Go/process collectors.
- `route` is the gin route template (`c.FullPath()`), or `unmatched` when there is none. It is never the raw path.

### CLI (arch-api)
- `arch-api serve`: starts the HTTP and metrics servers and shuts both down on SIGINT/SIGTERM.
- `arch-api migrate up`: applies the embedded goose migrations using `MIGRATE_DATABASE_URL` (default `DATABASE_URL`).
- `arch-api migrate status`: prints the applied and pending versions.
- Anything else: usage text, exit 2.

### Env (arch-api), read once in `internal/config` at start-up

| var | required | default | read by |
|---|---|---|---|
| `DATABASE_URL` | yes | — | `serve` (pgxpool); `migrate` when `MIGRATE_DATABASE_URL` is unset |
| `MIGRATE_DATABASE_URL` | no | `DATABASE_URL` | `migrate` only |
| `HTTP_ADDR` | no | `:8080` | `serve` |
| `METRICS_ADDR` | no | `:9090` | `serve` |
| `OIDC_ISSUER` | yes for `serve` | — | auth (`iss` check, discovery) |
| `OIDC_AUDIENCE` | yes for `serve` | — | auth (`aud` check) |
| `OIDC_JWKS_URL` | no | `jwks_uri` from `<OIDC_ISSUER>/.well-known/openid-configuration` | auth |
| `LOG_LEVEL` | no | `info` (`debug`/`info`/`warn`/`error`; other values are a start-up error) | logging |
| `CORS_ORIGINS` | no | empty | `serve` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | unset = tracing off | tracing |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | no | `grpc` (`grpc` or `http/protobuf`) | tracing |

A missing required variable, or an invalid value, makes the process print `config: <NAME> is required` (or `config: <NAME> is invalid`) to stderr and exit `1`. Several missing variables are named in one message.

### Runtime config (arch-web)
- At start-up the app fetches `GET /config.json` (same origin), shaped `{ "apiBaseUrl": string, "oidcAuthority": string, "oidcClientId": string }`.
- It falls back to `VITE_API_BASE_URL`, `VITE_OIDC_AUTHORITY` and `VITE_OIDC_CLIENT_ID` when the response isn't `ok`, isn't JSON, or lacks a key. Vite dev serves `index.html` for unknown paths, so a `200` HTML response must fall back too.
- `apiBaseUrl` is an origin. The client calls `${apiBaseUrl}/api/v1/me`.
- Every API call carries `Authorization: Bearer <access token>` and a fresh W3C `traceparent` (`00-<32 hex>-<16 hex>-01`).
- OIDC uses redirect URI `${origin}/auth/callback` and post-logout redirect URI `${origin}/`. Both match the realm's `http://localhost:5173/*`.

### Schema
- One goose migration, `migrations/00001_baseline.sql`, with no schema objects. goose creates its own `goose_db_version` table.
- No model tables, no grants, no `change_log`.
- `factory/repos.json` has no `rules`, so no other repo must change with it.

### Compatibility
- Nothing is deployed and there are no callers yet, so nothing needs to stay compatible.
- `arch-web` is generated from the merged `arch-api` contract, and from now on `Me` only gains optional fields.
- `/readyz` never writes to the database: it never creates `goose_db_version`. That keeps readiness working under the runtime role later.

## Requirements

### arch-api

**Module and layout**
1. `go.mod` sets module `github.com/CliXiD/arch-api`, `go 1.27` and `toolchain go1.27.2` ([ADR-0013]).
   - It has a `tool github.com/golangci/golangci-lint/v2/cmd/golangci-lint` directive (Decision 11).
   - `go.sum` is complete, so the gate's `-mod=readonly` builds pass.
   - A `.golangci.yml` (v2 format) enables at least the default linters plus `errcheck`, `gosec`, `revive` and `bodyclose`, and the code is clean under it.
2. Layout:
   - `cmd/arch-api/main.go`: the subcommand dispatch only.
   - `internal/config`: env parsing and validation.
   - `internal/auth`: JWKS cache, token validation, roles, the `Principal` type.
   - `internal/httpapi`: gin engine, Huma API, middleware, route registration, handlers.
   - `internal/health`: readiness checks behind small interfaces.
   - `internal/observability`: slog setup, Prometheus metrics, OTel setup.
   - `internal/db`: pgxpool and goose wiring.
   - `cmd/openapi/main.go`: prints the OpenAPI YAML to stdout, using the same route registration as `serve` without a database or Keycloak.

   Handlers stay thin. Claim mapping lives in `internal/auth`, readiness logic in `internal/health` (Factory notes, Conventions).

**Config**

3. Implement the env table in the Contract. `serve` requires `DATABASE_URL`, `OIDC_ISSUER` and `OIDC_AUDIENCE`. `migrate` requires only `MIGRATE_DATABASE_URL` or `DATABASE_URL`. Config error messages name the variable and never print its value ([SPEC-operations-05], [NFR-001]).
4. `.env.example` lists every variable in the table with the dummy values of `dev/env/arch-api.env`. `OIDC_JWKS_URL` and `OTEL_EXPORTER_OTLP_ENDPOINT` are commented out.

**Database and migrations**

5. `serve` creates a pgxpool from `DATABASE_URL` without blocking on connectivity, so the process starts and `/healthz` answers while the DB is down.
6. Migrations:
   - Embed them with `migrations/embed.go` (`package migrations`, `//go:embed *.sql`, exported `embed.FS`). This is a new file in the protected `migrations/` folder, as [ADR-0004] intends.
   - Add `migrations/00001_baseline.sql` with `-- +goose Up` / `-- +goose Down` and no schema objects (Decision 4). It may contain a no-op statement if goose needs one.
   - `migrate up|status` uses goose (v3) with the embedded FS and the `postgres` dialect.

**Health**

7. `GET /healthz` always returns `200 {"status":"ok"}`.
8. `GET /readyz` checks:
   - **database:** `Ping` within 2 s.
   - **migrations:** the highest applied version in `goose_db_version` equals the highest version in the embedded FS. It is read with a plain `SELECT`. A missing table counts as failing.

   It returns `200` or `503` per the Contract. It never creates or writes tables ([SPEC-operations-01]).

**Auth** ([SPEC-identity-access-02], [-03], [-07], [NFR-001])

9. Token validation in `internal/auth`:
   - It parses `Authorization: Bearer <jwt>`.
   - The JWT is verified against the JWKS at `OIDC_JWKS_URL`, or at the discovered `jwks_uri`. Discovery is lazy, on the first token, so start-up doesn't need Keycloak.
   - Allowed algorithms are RS256/RS384/RS512/PS256/ES256/ES384 and must match the JWK.
   - It checks `iss` == `OIDC_ISSUER`, and that `aud` (string or array) contains `OIDC_AUDIENCE`. `exp` and `nbf` allow 30 s of skew, and the clock is injectable for tests.
   - The keys are cached in memory. An unknown `kid` triggers exactly one refetch. Further unknown-`kid` refetches are rate-limited to at most one per 30 s, so a flood of bogus tokens can't hammer Keycloak.
   - A JWKS fetch error yields `401`. It is logged without the token.
   - Using `github.com/golang-jwt/jwt/v5` with a small cache of our own is acceptable. Any maintained library is fine if the refetch count is observable in tests.
10. Roles and teams:
    - Effective roles come from `realm_access.roles`: `admin` adds `editor` and `viewer`, `editor` adds `viewer`. Other role names are ignored. The output order is always `viewer, editor, admin`.
    - `teams` comes from the `teams` claim, or `[]` when absent.
11. Service accounts: `actor_kind` is `service` when the token has a `client_id` claim, or its `preferred_username` starts with `service-account-`. The client id is `client_id`, else `azp`, and `subject` and `name` are that client id. Otherwise `actor_kind` is `user`, `subject` is `sub`, `name` is `name` or else `preferred_username`, and `email` is `email` or `""`.
12. Default deny (Decision 10):
    - Every Huma operation is registered through one helper, e.g. `register(api, op, minRole, handler)`. It records the minimum role in `op.Metadata` and sets the bearer `Security` on `/api/v1` operations.
    - The minimum role is one of `public`, `viewer`, `editor` or `admin`. `public` is allowed only for `/healthz` and `/readyz`.
    - An API-wide Huma middleware enforces it: `401` without a valid token, `403` when the role is too low. An operation without a declared role gets `403` at runtime.
    - The authenticated `Principal` is put in the request context for handlers and the request log.
13. Problems: `401` and `403` use the shapes in the Contract, with `Content-Type: application/problem+json`. Huma's default error model may stay for other statuses. Huma's default `$schema` link transformer is removed, and `OpenAPIPath`, `DocsPath` and `SchemasPath` are empty.

**API**

14. `GET /api/v1/me` (min role `viewer`) returns `Me` from the `Principal` ([SPEC-identity-access-08]).
15. CORS per the Contract, with `gin-contrib/cors` or an equivalent, mounted before auth.

**Observability**

16. Logging:
    - It uses `log/slog` with the JSON handler on stdout, at `LOG_LEVEL`.
    - Request middleware writes one line per request: `msg:"request"`, `method`, `route` (template or `unmatched`), `status`, `duration_ms`, `trace_id` (empty when tracing is off), and `actor` (the principal's subject, empty when unauthenticated).
    - It never logs headers, query strings, bodies, tokens or claim values other than the subject ([SPEC-operations-03]).
17. Metrics per the Contract, on a separate `http.Server` at `METRICS_ADDR` with `promhttp` ([SPEC-operations-02]). The DB pool gauges come from `pool.Stat()` in a custom collector.
18. Tracing only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set ([SPEC-operations-04]):
    - OTLP trace exporter over gRPC or HTTP per `OTEL_EXPORTER_OTLP_PROTOCOL`, resource `service.name=arch-api`.
    - W3C TraceContext propagator, so an incoming `traceparent` continues the trace.
    - `otelgin` middleware, and `otelpgx` as the pgx tracer. Query arguments are never recorded.
    - When unset, no exporter is created and no network calls are made.

**OpenAPI and tooling**

19. Makefile:
    - `make openapi` runs `go run ./cmd/openapi > api/openapi.yaml`.
    - `make openapi-check` generates into a `mktemp` file, `diff`s it against `api/openapi.yaml`, removes the temp file, and exits non-zero on any difference. It never writes a tracked file (Decision 12).
    - Commit the generated `api/openapi.yaml`, which is OpenAPI 3.1 and deterministic: the same output on every run.
20. Add `.github/workflows/ci.yml`, a new file:
    - It runs on `pull_request` and on `push` to `main`.
    - `actions/setup-go` with `go-version-file: go.mod`, then `go vet ./...`, `go tool golangci-lint run ./...`, `go test -count=1 ./...`, `go build ./...` and `make openapi-check` (Decision 7, [ADR-0010]).

**Tests** (table-driven, `testing` + testify, no network or DB)

21. `internal/auth`: an `httptest` JWKS server with generated keys. It covers:
    - valid
    - no token
    - malformed / non-Bearer
    - `alg: none` and HS256
    - bad signature
    - wrong issuer
    - wrong audience (string and array)
    - expired 31 s (rejected)
    - expired 29 s (accepted)
    - unknown `kid` → exactly one refetch, then accepted when the new key is present
    - a second unknown `kid` within 30 s → no extra refetch, `401`
22. Roles and claims:
    - `admin` → `["viewer","editor","admin"]`.
    - `editor` + group → `teams: ["platform"]`.
    - No arch role → `403 /problems/forbidden` from `/api/v1/me`.
    - A client-credentials-shaped token (`client_id`, `azp=arch-ci-platform`, `preferred_username=service-account-arch-ci-platform`) → `actor_kind: "service"`, `subject: "arch-ci-platform"`.
23. Routes and problems:
    - A route-registry test walks every operation in the Huma OpenAPI document. It fails when one lacks a declared minimum role, or when `public` is used outside `/healthz` and `/readyz`.
    - `401`/`403` responses have `Content-Type: application/problem+json` and the Contract `type`.
24. Health and process:
    - `internal/health`, with fakes: ping fails → `503 ["database"]`; version behind or table missing → `503 ["migrations"]`; both fine → `200`.
    - Config: missing `OIDC_ISSUER` → an error naming `OIDC_ISSUER`.
    - The metrics handler isn't registered on the main engine (`GET /metrics` → `404`).
25. Logging: the test sends a request with `Authorization: Bearer <token>` through the middleware into a buffer handler. It asserts the line has every field in Requirement 16 and contains neither the token nor `Authorization`.

**Docs**

26. `README.md` covers: what the service is; prerequisites (Go 1.27, the hub dev stack); running it (`dev/bin/stack up`, `dev/bin/apply-env arch-api`, `go run ./cmd/arch-api migrate up`, `go run ./cmd/arch-api serve`); the env table; the endpoints; `make openapi` / `make openapi-check`; the check commands; and links to the hub specs and ADRs.

### arch-web

**Project**

27. Tooling:
    - `package.json` has `"packageManager": "pnpm@<current 10.x>"`, `"engines": { "node": ">=26" }`, `.nvmrc` with `26` ([ADR-0013]), and a committed `pnpm-lock.yaml`.
    - Scripts: `dev` (`vite`), `build` (`vite build`), `lint` (`eslint .`), `typecheck` (`tsc --noEmit`, or `tsc -b --noEmit` for project references), `test` (`vitest run`), `gen:api`.
    - Stack: React 19, Vite, TypeScript strict, Tailwind 4 via `@tailwindcss/vite`, React Router 7, TanStack Query, `oidc-client-ts`, `openapi-fetch`, and `openapi-typescript` as a dev dependency ([ADR-0007]).
    - ESLint flat config with `typescript-eslint` and `eslint-plugin-react-hooks`. It ignores `dist/` and `src/api/schema.d.ts`.
    - Vitest runs in `jsdom` with `@testing-library/react`, `@testing-library/user-event` and `@testing-library/jest-dom`.
28. `gen:api` runs `openapi-typescript ${ARCH_API_OPENAPI:-../arch-api/api/openapi.yaml} -o src/api/schema.d.ts`, the sibling path in both `repos/` and `.worktrees/<job>/`. Commit `src/api/schema.d.ts` generated from this job's `arch-api` branch and never hand-edit it.
29. `.env.example` lists `VITE_API_BASE_URL`, `VITE_OIDC_AUTHORITY` and `VITE_OIDC_CLIENT_ID` with the values of `dev/env/arch-web.env`. Do not add `public/config.json`.

**Config and API client**

30. `src/config.ts` loads the runtime config per the Contract, before the app renders. When neither source yields all three keys, the page shows "Architecture E2E is not configured: missing <keys>".
31. `src/api/client.ts`: an `openapi-fetch` client typed by `paths` from `schema.d.ts`. It has `baseUrl = apiBaseUrl` and a middleware that adds `Authorization: Bearer` from the in-memory user, plus a fresh `traceparent` generated with `crypto.getRandomValues` ([SPEC-operations-04]). `src/api/me.ts` exposes a TanStack Query hook `useMe()` for `GET /api/v1/me`.

**Auth** ([SPEC-identity-access-01], [-09])

32. `src/auth/` wraps one `UserManager`:
    - `response_type: "code"` (PKCE), `scope: "openid profile email"`, redirect URIs per the Contract, `automaticSilentRenew: true` (refresh-token renewal).
    - `userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() })`, so tokens never touch Web Storage. The default `stateStore` keeps only the transient PKCE state across the redirect, and `oidc-client-ts` removes it on callback.
    - It is exposed through a React context and a `useAuth()` hook so tests can inject a fake.
33. Sign-in flow:
    - **No user:** any route except `/auth/callback` renders "Signing in…" (`role="status"`) and calls `signinRedirect({ state: { returnTo: pathname + search + hash } })`.
    - **Failure:** when the redirect, or the metadata discovery behind it, fails, show "Sign-in is unavailable, try again" with a "Try again" button that retries.
    - **Callback:** `/auth/callback` calls `signinRedirectCallback()`, then `navigate(returnTo ?? "/", { replace: true })`. A callback error shows the same unavailable state.
34. Refresh and sign-out:
    - **Refresh failure:** on `addSilentRenewError`, or a `401` from the API, remove the user and call `signinRedirect` with the current route as `returnTo`.
    - **Sign out:** calls `signoutRedirect({ id_token_hint })` and `removeUser()`, which clears the tokens. Coming back to `/` with no session starts sign-in, which shows Keycloak's sign-in page.

**Shell** ([SPEC-identity-access-03], [-08], [NFR-006], [NFR-007])

35. Router: `createBrowserRouter`, client-side only. `/auth/callback` is the callback, and `*` renders the shell behind the auth guard.
36. Shell:
    - A `<header>` containing an `<h1>` (or banner text) "Architecture E2E" and the user menu, and `<main>` saying "The landscape is coming soon."
    - The user menu is a button labelled with `me.name` (`aria-expanded`, `aria-controls`). It opens a panel showing "Roles: viewer, editor", "Teams: platform" ("Teams: none" when empty) and a "Sign out" button.
    - Tailwind classes only. It must be keyboard operable.
37. States of `/me`:
    - **Loading:** "Loading…" (`role="status"`) in place of the menu.
    - **`403`:** the whole body is replaced with "You don't have access to Architecture E2E; ask an admin" plus the "Sign out" button.
    - **Other errors:** "Couldn't load your profile" with a "Try again" button that refetches.

**CI and tests**

38. Add `.github/workflows/ci.yml`, a new file:
    - It runs on `pull_request` and on `push` to `main`.
    - `pnpm/action-setup`, then `actions/setup-node` with `node-version-file: .nvmrc` and `cache: pnpm`, then `pnpm install --frozen-lockfile`, `pnpm run lint`, `pnpm run typecheck`, `pnpm run test` and `pnpm run build`.
    - The build step sets the three `VITE_*` vars to the `.env.example` values.
39. Vitest + Testing Library tests, queried by role or label, with a fake `useAuth`/`UserManager` and stubbed `fetch`. They cover:
    - "Signing in…" while redirecting, and `signinRedirect` called with the current route as `returnTo`.
    - "Sign-in is unavailable, try again" with a "Try again" button when discovery fails; clicking it retries.
    - The callback navigates to `returnTo`.
    - The user menu shows name, roles and teams after `/me`.
    - The no-access message on `403`.
    - A silent-renew error triggers `signinRedirect` with the current route.
    - "Sign out" calls `signoutRedirect` and `removeUser`.
    - The API client sends `Authorization: Bearer` and a `traceparent` matching `^00-[0-9a-f]{32}-[0-9a-f]{16}-01$`.
    - Config falls back to `VITE_*` when `/config.json` returns HTML.
    - Tokens are held in memory only: after a completed sign-in with the real `UserManager` config (stubbed network), `localStorage` is empty and no `sessionStorage` key or value contains the access, refresh or ID token.

**Docs**

40. `README.md` covers: prerequisites (Node 26, pnpm, the hub dev stack); running it (`dev/bin/stack up`, `dev/bin/apply-env arch-web`, `pnpm install`, `pnpm dev`); `/config.json` and the `VITE_*` fallback; `pnpm gen:api` and `ARCH_API_OPENAPI`; the check scripts; and links to the hub specs and ADRs.

## Acceptance criteria

1. [arch-api] Token validation tests pass and include each case in Requirement 21. Check: `go test -count=1 -v ./internal/auth/...` shows subtests for valid, no token, bad signature, wrong issuer, wrong audience, expired 31 s (rejected), expired 29 s (accepted) and unknown `kid` (one refetch).
2. [arch-api] Role tests pass. Check: `go test -count=1 -v ./internal/...` includes a case where an `admin` token's `/api/v1/me` returns `roles: ["viewer","editor","admin"]`, and one where a token with no arch role gets `403` with `type: /problems/forbidden`.
3. [arch-api] The route-registry test fails without a role declaration. Check: temporarily register an operation without a minimum role and run `go test ./internal/httpapi/...`; it fails and names the operation.
4. [arch-api] Against the local stack (`dev/bin/stack up`, `dev/bin/apply-env --to <worktree> arch-api`, `go run ./cmd/arch-api migrate up`, `go run ./cmd/arch-api serve`):
   - `curl -i localhost:8080/api/v1/me` → `401`, `Content-Type: application/problem+json`, `"type":"/problems/unauthenticated"`.
   - With the `editor` user's token → `200` with `"teams":["platform"]` and `"roles":["viewer","editor"]`.
   - With a token from `curl -s -d grant_type=client_credentials -d client_id=arch-ci-platform -d client_secret=dev-ci-secret localhost:8180/realms/arch/protocol/openid-connect/token` → `200` with `"actor_kind":"service"` and `"subject":"arch-ci-platform"`.
5. [arch-api] On a fresh DB (`dev/bin/stack reset`), with `serve` running before `migrate up`:
   - `curl -i localhost:8080/readyz` → `503 {"status":"unavailable","failing":["migrations"]}`.
   - After `go run ./cmd/arch-api migrate up` it returns `200 {"status":"ok"}`.
   - `curl localhost:8080/healthz` → `200 {"status":"ok"}` both times.
   - With Postgres stopped, `/readyz` → `503` with `failing: ["database"]`.
6. [arch-api] `curl localhost:9090/metrics` lists `http_requests_total` and `db_pool_total_connections`, and `curl -i localhost:8080/metrics` → `404`.
7. [arch-api] Running `env -u OIDC_ISSUER go run ./cmd/arch-api serve` (with the other vars set) exits non-zero and prints a message containing `OIDC_ISSUER`.
8. [arch-api] The logging test passes. Check: `go test -count=1 -v ./internal/...` includes a test asserting the request log line has `method`, `route`, `status`, `duration_ms`, `trace_id` and `actor`, and contains neither the bearer token nor `Authorization`.
9. [arch-api] OpenAPI generation:
   - `make openapi` followed by `git status --porcelain` shows no change on the branch.
   - After `echo '# stale' >> api/openapi.yaml`, `make openapi-check` exits non-zero, and `git status --porcelain` shows only `api/openapi.yaml` modified and no new files. Then run `git checkout api/openapi.yaml`.
   - `api/openapi.yaml` starts with `openapi: 3.1` and contains `/api/v1/me`, `/healthz`, `/readyz`, a bearer security scheme, and no `/docs` or `/openapi` path.
10. [arch-api] `go.mod` contains `go 1.27`, a `toolchain go1.27` line and `tool github.com/golangci/golangci-lint/v2/cmd/golangci-lint`. `go tool golangci-lint version` prints the pinned version.
11. [arch-api] `FACTORY_HUB=<hub> FACTORY_REPO_KEY=arch-api FACTORY_BASE=main bash <hub>/factory/checks/arch-api.sh` exits `0` in the worktree.
12. [arch-api] `.github/workflows/ci.yml` triggers on `pull_request` and runs `go vet`, `go tool golangci-lint run`, `go test`, `go build` and `make openapi-check`.
13. [arch-api] `.env.example` contains every variable in the Contract env table, and `README.md` documents the commands and endpoints.
14. [arch-web] `pnpm run test` passes and includes tests (Requirement 39) asserting:
    - "Signing in…" while redirecting.
    - "Sign-in is unavailable, try again" with a "Try again" button when discovery fails.
    - The user menu showing name, roles and teams after `/me`.
    - The no-access message on `403`.
15. [arch-web] A test asserts that after sign-in `localStorage` is empty and `sessionStorage` holds no token. Check: `pnpm vitest run -t "memory"`, or the test's name, passes.
16. [arch-web] A test asserts that a silent-renew failure calls `signinRedirect` with the current route, and that "Sign out" calls `signoutRedirect` and clears the user.
17. [arch-web] With the stack and `arch-api` running and `pnpm dev`:
    - Opening `http://localhost:5173/some/route` shows "Signing in…", then Keycloak.
    - Signing in as `editor`/`password` returns to `/some/route` and shows the header "Architecture E2E", "The landscape is coming soon." and a user menu with "Editor Local", "Roles: viewer, editor" and "Teams: platform".
    - The browser's network tab shows `GET /api/v1/me` with `Authorization` and `traceparent` headers.
    - "Sign out" ends on Keycloak's sign-in page.
18. [arch-web] Running `pnpm gen:api` in the worktree (sibling `../arch-api` is this job's branch), then `git status --porcelain src/api/schema.d.ts`, shows no change. The file starts with openapi-typescript's generated-file header.
19. [arch-web] `FACTORY_HUB=<hub> FACTORY_REPO_KEY=arch-web FACTORY_BASE=main bash <hub>/factory/checks/arch-web.sh` exits `0` in the worktree.
20. [arch-web] `.github/workflows/ci.yml` triggers on `pull_request` and runs `pnpm run lint`, `pnpm run typecheck`, `pnpm run test` and `pnpm run build` on the Node from `.nvmrc`.
21. [arch-web] `.nvmrc` contains `26`, `package.json` has `engines.node` `>=26`, and there is no `public/config.json`.

## Merge and deploy order

`arch-api` first, then `arch-web` (`merge_order`).
- `arch-web`'s `src/api/schema.d.ts` is generated from `arch-api`'s `api/openapi.yaml`. If `arch-api` changes in review, `arch-web` must regenerate before merging.
- Nothing is deployed in this slice. Locally, `arch-web` needs a running `arch-api` for the shell.
- Both PRs are merged by a human ([ADR-0002]).

## Out of scope

- Any model table, endpoint or screen (nodes, edges, types, teams, environments, history, landscape).
- Grants for `arch_app`, `change_log`, triggers, sqlc setup and queries.
- Any change to `arch-deploy` (Dockerfiles, Helm, realm export), to the hub (`dev/`, `factory/checks/`, `dev/keycloak/arch-realm.json`), or to `factory/repos.json`.
- Playwright e2e, `testcontainers-go` integration tests, the `arch` CLI (`cmd/arch`), and the YAML JSON Schema or `/schema/arch.json`.
- Production concerns: the OTLP backend choice, Docker images, nginx config, serving `config.json`.
- These extras:
  - An `openapi` subcommand on `arch-api` (use `cmd/openapi`).
  - Swagger UI or docs routes.
  - A user table or user cache.
  - Silent sign-in via an iframe.
  - Persisting tokens across reloads.
  - The OTel web SDK in `arch-web`.
  - shadcn/ui components.
  - Feature flags.
  - Extra config options.
- Editing any existing file under `.github/*` or `migrations/*`. Only new files are created there.

## Assumptions

- **Service detection.** A service-account token is one with a `client_id` claim or a `service-account-` `preferred_username`. Its `subject` and `name` are the client id. Keycloak 26 marks service-account tokens this way, and [SPEC-identity-access-07] makes the client id the actor.
- **`migrate` needs only a database URL.** Migrations run as a Helm hook later and shouldn't need OIDC settings.
- **Required variables.** `DATABASE_URL`, `OIDC_ISSUER` and `OIDC_AUDIENCE` are required; every other variable has a default. That matches the issue (only `OIDC_JWKS_URL` and `OTEL_EXPORTER_OTLP_ENDPOINT` are marked optional) while giving the addresses and log level sane defaults.
- **Lazy discovery.** JWKS discovery waits for the first token, and readiness doesn't check Keycloak. The issue's `/readyz` contract lists only `database` and `migrations`.
- **JWKS refetch limit.** Unknown-`kid` refetches are limited to one per 30 s. Without a limit, a flood of bogus tokens would hammer Keycloak; the issue asks only for "one refetch".
- **Baseline migration.** The file is `migrations/00001_baseline.sql`, using goose sequential numbering. It is empty per Decision 4, and the `arch_app` SELECT grant on `goose_db_version` comes with the write-API slice.
- **OpenAPI generator.** It is a separate `cmd/openapi` program, so the CLI keeps exactly the issue's `serve` and `migrate up|status`.
- **Metric names.** `http_requests_total`, `http_request_duration_seconds` and the `db_pool_*` gauges are my choice; the documents name the metrics but not their names.
- **Session storage.** The PKCE `state`/`code_verifier` stays in `sessionStorage` only during the redirect; `oidc-client-ts` needs it across the page load and removes it on callback. The "nothing written" criterion is read as no tokens in Web Storage and an empty `localStorage`, which is what [SPEC-identity-access-01] Non-functional requires.
- **Reloads re-sign-in.** A page reload loses the session and redirects to Keycloak, which returns at once while the SSO session lives. This follows from tokens in memory only.
- **Router mode.** React Router 7 runs in library mode (`createBrowserRouter`) rather than framework "SPA mode". It is client-side only either way, needs less tooling, and [ADR-0007] doesn't name the mode's mechanics. The approver may flag this as an ADR reading.
- **UI copy.** "Loading…", "Couldn't load your profile", "Architecture E2E is not configured: missing …", "Roles: …" and "Teams: none" aren't in the issue. Grill checklist asks for empty, loading and error states.
- **`traceparent`.** It is generated by hand, not with the OTel web SDK. That is enough for [SPEC-operations-04], and the API starts the trace when tracing is on.
- **`gen:api` source.** It reads `../arch-api/api/openapi.yaml`, overridable with `ARCH_API_OPENAPI`. Both `repos/` and the job worktrees keep the repos as siblings.
- **Go module path.** `github.com/CliXiD/arch-api`, from the repo's remote.

## Docs impact

- `docs/specs/001_identity-access.md`:
  - [SPEC-identity-access-08] and Interfaces: write `GET /api/v1/me` (Decision 3).
  - Interfaces: replace the web config names `OIDC_AUTHORITY`/`OIDC_CLIENT_ID`/`API_BASE_URL` with `/config.json` `apiBaseUrl`/`oidcAuthority`/`oidcClientId` plus the `VITE_*` fallback.
  - Note that a service account's `subject` is its client id.
- `docs/specs/009_operations.md`:
  - Interfaces: add `OIDC_JWKS_URL` (optional), and the defaults for `HTTP_ADDR`, `METRICS_ADDR` and `LOG_LEVEL`.
  - [SPEC-operations-01]: name the `/readyz` body `{"status","failing":["database"|"migrations"]}`.
  - [SPEC-operations-02]: list the metric names.
- No new ADR. A short ADR note may be needed only if the approver decides library-mode React Router departs from [ADR-0007].

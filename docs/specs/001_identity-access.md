# Spec 001: identity-access

> Status: Draft · Implements: [BR-040], [BR-041], [BR-043], [NFR-001] · Decisions: [ADR-0008], [ADR-0003], [ADR-0012]
> Repos: arch-api, arch-web, arch-deploy · Last reviewed: 2026-11-08

## Summary

Who can use the tool and what they may do. Every user signs in with the organisation's
Keycloak; nothing is visible without a valid session. Roles come from the token: viewer,
editor and admin. Editor rights are limited to nodes owned by the user's teams. CI pipelines
use a service account. Every later spec relies on the `actor` and permission checks defined here.

## Behaviour

- **SPEC-identity-access-01** An unauthenticated visitor to any `arch-web` route is redirected to Keycloak (Authorization Code + PKCE) and returned to the route they asked for after signing in. While the redirect is in progress the app shows a "Signing in…" state; if Keycloak is unreachable it shows "Sign-in is unavailable, try again" with a retry button. [BR-040] [NFR-001]
- **SPEC-identity-access-02** `arch-api` rejects every request without a valid bearer token with `401` (RFC 9457 problem, `type: /problems/unauthenticated`). A token is valid when its signature checks against the realm JWKS (cached, refreshed on unknown `kid`), `iss` matches the configured issuer, `aud` contains the API client id, and it has not expired (30 s clock skew allowed). Only `/healthz`, `/readyz` and `/metrics` are public. While the API has never loaded the realm's signing keys (Keycloak unreachable since start-up), it returns `503` (`type: /problems/auth-unavailable`, `Retry-After: 5`) instead of `401`; refetches on an unknown `kid` happen at most once per 30 s, and failed fetches retry no sooner than 5 s. [NFR-001]
- **SPEC-identity-access-03** Roles are read from the realm roles in the token: `viewer`, `editor` and `admin`. `admin` implies `editor`, and `editor` implies `viewer`. `viewer` is the realm default role, so every signed-in user has it; a user with none of these roles (for example, removed by an admin) gets `403` from the API, and the web app shows "You don't have access to Architecture E2E; ask an admin". [BR-040]
- **SPEC-identity-access-04** A viewer can read every node, edge, type, team and history entry. [BR-040]
- **SPEC-identity-access-05** An editor can create, update and delete nodes whose owner team is one of the teams in the token's `teams` claim, and edges whose source node they can edit. Any other write returns `403` (`type: /problems/forbidden`) with the owning team named in `detail`. The web app hides or disables edit actions the user can't perform and shows the owning team. [BR-040]
- **SPEC-identity-access-06** An admin can do everything an editor can on every node and edge, and can also manage types, teams and settings ([BR-041], detailed in the admin spec). [BR-040] [BR-041]
- **SPEC-identity-access-07** A CI pipeline gets a token with client credentials from a confidential Keycloak client. The service account has the realm role `editor` and a `teams` claim set on the client, so it can only push YAML for those teams. A token is a service account only when its `client_id` claim (a user-session-note mapper on each CI client) equals its `azp`; the username is never used. Changes it makes are recorded with `actor_kind: service` and the client id as actor. [BR-043]
- **SPEC-identity-access-08** `GET /me` returns the caller's identity and permissions, and the web app uses it to show the user menu and decide which actions to enable. [BR-040]
- **SPEC-identity-access-09** Signing out ends the Keycloak session (RP-initiated logout) and clears the tokens held by the web app. When the access token expires mid-session, the web app refreshes it silently; if the refresh fails, the user is sent back to sign in and returns to the same route. [BR-040]

## Interfaces

- `GET /me` → `200 { "subject": "string", "name": "string", "email": "string", "roles": ["viewer"|"editor"|"admin"], "teams": ["string"], "actor_kind": "user"|"service" }`
- Errors on every endpoint: `401 /problems/unauthenticated`, `403 /problems/forbidden` (RFC 9457 `application/problem+json`).
- `arch-web` config (build-time or `/config.json` at runtime): `OIDC_AUTHORITY`, `OIDC_CLIENT_ID`, `API_BASE_URL`.
- `arch-api` config: `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` (optional; discovered from the issuer by default).
- Keycloak realm `arch` (exported in `arch-deploy`): public client `arch-web` (PKCE, redirect URIs per environment), bearer-only `arch-api`, confidential clients `arch-ci-<team>`; realm roles `viewer`, `editor`, `admin`; group mapper → `teams` claim (group names, without the path).

## Data

- No user table: identity comes from the token. `actor` in [ADR-0005]'s `change_log` is the token `sub` plus a cached display name (`preferred_username`).
- Team names in the `teams` claim must match `teams.id` in the model (see the model spec and [SPEC-admin-04]); a claim naming an unknown team grants nothing.

## Non-functional

- [NFR-001]: default deny. Every API route declares its minimum role, and a route without a declaration fails a unit test.
- Tokens and the `Authorization` header are never logged ([ADR-0011]); the web app keeps tokens in memory only, not in localStorage.
- Client secrets for CI clients live in each team's CI secret store, never in a repo ([ADR-0012]).

## Open questions

- None. Settled in /hub-init 2026-11-08: edges belong to the side of their source node
  ([SPEC-identity-access-05]); `viewer` is the realm default role, so every signed-in user can read.

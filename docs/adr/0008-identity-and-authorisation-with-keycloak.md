# ADR-0008: Identity and authorisation with Keycloak

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-040], [BR-043], [NFR-001]

## Context

All access requires SSO ([BR-040], [NFR-001]); CI pushes need a non-personal identity ([BR-043]).
The organisation uses Keycloak. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **Keycloak OIDC, roles in the token, team scope from a group claim** — no user store in the app.
2. **App-managed roles** in the database keyed by the OIDC subject — more flexible, more admin UI.

## Decision

Option 1. `arch-web` signs in with Authorization Code + PKCE; `arch-api` validates JWTs against
the realm's JWKS (issuer and audience checked). Realm roles `viewer`, `editor`, `admin`; a
`teams` group claim scopes editor rights to nodes owned by those teams. CI uses a confidential
client with client credentials and a service-account role. The realm is exported in
`arch-deploy` and seeded in the local stack.

## Consequences

- Every endpoint declares its role; the default is deny.
- Team names in Keycloak groups must match `teams` in the model.

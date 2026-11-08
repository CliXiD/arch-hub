# ADR-0003: Backend language and HTTP framework

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-011], [BR-030], [NFR-005]

## Context

The backend serves a REST API to the SPA and to CI pipelines (YAML push). The frontend's client is
generated from the API's spec, so the spec must come from the code and stay current. The owner
chose Go with gin and OpenAPI 3.1 generated from code. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **Huma v2 on gin (`humagin`)** — typed handlers, OpenAPI 3.1 from Go types, validation from
   struct tags, RFC 9457 errors; keeps gin and its middleware. Mature.
2. **Fuego** — OpenAPI 3.1 from types on net/http; gin adapter experimental; younger project.
3. **swaggest/rest** — OpenAPI 3.0/3.1, on chi rather than gin; verbose.
4. **swaggo/swag v2** — gin with comment annotations; 3.1 support partial and still RC; comments drift.
5. **Spec-first (oapi-codegen, ogen, Goa)** — the spec drives the code, the opposite of what was asked.

## Decision

Go 1.25 (pinned with `go` and `toolchain` in `go.mod`), **gin + Huma v2**. The OpenAPI 3.1 spec is
exported to `arch-api/api/openapi.yaml` by `make openapi`; CI fails when the committed file is
stale. Errors use RFC 9457 problem details. Lint with a pinned `golangci-lint`.

## Consequences

- `arch-web` generates its types from `api/openapi.yaml` ([ADR-0007]); a contract change starts
  in `arch-api`.
- `api/openapi.yaml` is generated: never edited by hand.

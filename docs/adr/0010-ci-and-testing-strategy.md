# ADR-0010: CI and testing strategy

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [NFR-005]

## Context

The factory's gate runs lint, typecheck, unit tests and build only; anything needing services
runs in CI or locally. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **GitHub Actions per repo, unit tests in the gate, integration and e2e in CI only**.
2. **One central pipeline** — doesn't fit three independent repos.

## Decision

- `arch-api`: `golangci-lint run`, `go vet`, `go test ./...` (unit), `go build ./...`, OpenAPI
  staleness check; integration tests with `testcontainers-go` behind `//go:build integration`, in
  CI only.
- `arch-web`: ESLint, `tsc --noEmit`, Vitest, `vite build`; Playwright e2e against the compose
  stack, outside the gate.
- `arch-deploy`: `helm lint`, `helm template | kubeconform`.

## Consequences

- Factory check scripts mirror these gate steps once each repo has its first code.

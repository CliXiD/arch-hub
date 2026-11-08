# ADR-0013: Runtime versions

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-dev-stack 2026-11-08
- Relates to: [ADR-0003], [ADR-0007], [NFR-001]

## Context

[ADR-0003] pinned Go 1.25 and [ADR-0007] pinned Node 22 LTS. Checked against go.dev and
nodejs.org on 2026-11-08: Go 1.27.3 is current and Go supports only the two newest releases
(1.27, 1.26), so 1.25 no longer gets security fixes; Node 26 ("Lithium") is the active LTS and
Node 22 reaches end of life in April 2027. No code exists yet, so changing now costs nothing.
Source: decided in /hub-dev-stack on 2026-11-08.

## Options considered

1. **Go 1.27 + Node 26 LTS** — both on supported, current lines for the longest time.
2. **Go 1.27, keep Node 22** — Node upgrade needed within months.
3. **Keep Go 1.25 + Node 22** — Go already unsupported.

## Decision

Option 1. This supersedes only the runtime versions in [ADR-0003] and [ADR-0007]; everything
else in them stands.

- `arch-api`: `go 1.27` and `toolchain go1.27.x` in `go.mod`; images `golang:1.27-*` to build,
  distroless static to run.
- `arch-web`: Node 26 LTS in `.nvmrc` (`26`), `engines.node: ">=26"`; images `node:26-alpine`.

## Consequences

- Dev stack images: `golang:1.27.2-alpine`, `node:26.12.1-alpine` (moved to the newest patch
  once it is two weeks old).
- When a newer Go is released, move to it before the older of the two supported releases
  loses support; Node follows the active LTS line.

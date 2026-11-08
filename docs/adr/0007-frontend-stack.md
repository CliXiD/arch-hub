# ADR-0007: Frontend stack

- Status: Accepted (runtime version superseded by [ADR-0013])
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-020], [BR-021], [BR-030], [NFR-005], [NFR-006]

## Context

The UI is a SPA with client-side routes, built around an interactive graph that must render
2,000 nodes / 10,000 edges in under 3 seconds ([NFR-005]) and meet WCAG 2.1 AA for its shell
([NFR-006]). The owner chose React with TailwindCSS. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **React 19 + Vite + React Flow (xyflow) + ELK.js** — mature graph canvas with custom nodes;
   ELK gives layered layouts for chains.
2. **Cytoscape.js** — strong graph analytics and performance, less natural for rich React nodes.
3. **D3 by hand** — full control, much more code.

## Decision

React 19, Vite, TypeScript, TailwindCSS 4, React Router 7 in SPA mode, TanStack Query,
React Flow + ELK.js (layout in a web worker), shadcn/ui, `oidc-client-ts`; API types from
`openapi-typescript` + `openapi-fetch` over `arch-api/api/openapi.yaml`. Node 22 LTS pinned in
`.nvmrc`, pnpm. Vitest + Testing Library for unit tests; Playwright e2e against the local stack.

## Consequences

- The generated API types are regenerated whenever `openapi.yaml` changes; never hand-edited.
- The graph canvas needs a list alternative for accessibility.

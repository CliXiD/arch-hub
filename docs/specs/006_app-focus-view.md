# Spec 006: app-focus-view

> Status: Draft · Implements: [BR-021], [NFR-005], [NFR-006] · Decisions: [ADR-0007], [ADR-0004]
> Repos: arch-web, arch-api · Last reviewed: 2026-11-08

## Summary

"From the point of view of an application" [S-001]: one node in the middle, showing what it
runs on, where it stores data, what it calls and over which network path, and what calls it.

## Behaviour

- **SPEC-app-focus-view-01** `/nodes/{env}/{id}` shows the node's details (name, type, owner, tags, attributes, source, last change) and a focus graph of its direct neighbours, grouped into columns: **Calls / depends on** (outgoing `calls` and `depends_on`), **Runs on** (`runs_on`), **Stores data in** (`stores_data_in`), **Called by / depended on by** (incoming `calls` and `depends_on`), and **Owned by**. [BR-021]
- **SPEC-app-focus-view-02** For each outgoing `calls` edge, the view also shows the network path, built from `routes_via` edges: from the caller, the chain of network elements it routes via, then the target. For example, `payments-api → vpc-prod → landing-zone → direct-connect → core-banking (on-prem)`. Path elements are shown in order and can be clicked. If a `calls` edge has no route, it says "No network path modelled". [BR-021] [S-001]
- **SPEC-app-focus-view-03** A depth control (1–3, default 1) expands the neighbours transitively in both directions. [BR-021]
- **SPEC-app-focus-view-04** The page has tabs for **Overview** (the focus graph), **Edges** (a table of every incoming and outgoing edge with its attributes) and **History** ([SPEC-editing-history-07]), plus actions **Impact** (007) and **Edit** (003, if permitted). [BR-021] [BR-042]
- **SPEC-app-focus-view-05** For an unknown node it shows "Node <env>/<id> not found", with a link back to the landscape. [BR-021]

## Interfaces

- `GET /api/v1/nodes/{environment}/{id}/neighbourhood?depth=1..3` → `{ "node", "nodes": [...], "edges": [...], "paths": [{ "edge_uid", "via": ["<node id>", ...] }] }`.
- `routes_via` modelling: an edge `routes_via` from an application to a network element means "its outbound calls go through this element". Network elements chain to each other with `routes_via`, and the last element links to the target's network or to the target node. The path for a `calls` edge A → B is the shortest `routes_via` chain from A that reaches B or one of B's network elements.

## Data

- None owned.

## Non-functional

- [NFR-005]: the neighbourhood at depth 3 returns in under 1 s.
- [NFR-006]: the Edges tab is the accessible alternative to the focus graph.

## Open questions

- Is the `routes_via` path model above expressive enough for real landing-zone setups (for example several paths per call, or paths per port)? Revisit after the first teams model theirs. — khajonpot

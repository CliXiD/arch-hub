# Spec 002: model

> Status: Draft · Implements: [BR-001], [BR-002], [BR-003], [BR-004], [NFR-002] · Decisions: [ADR-0004], [ADR-0005]
> Repos: arch-api · Last reviewed: 2026-11-08

## Summary

The E2E architecture is a typed graph. **Types** define what nodes and edges can exist and
which attributes they carry, **teams** own nodes, and **nodes** and **edges** are the
instances, each in one environment. Every later spec reads and writes this model.

## Behaviour

- **SPEC-model-01** Every node has a `kind` (one of the fixed kinds `application`, `infrastructure`, `network`, `external`, `team`) and a `type` (an admin-defined subtype of a kind, for example `eks-cluster`, `rds-postgres` and `landing-zone`). A node's type fixes its kind. [BR-001] [BR-003]
- **SPEC-model-02** The model is seeded with the default types from [BR-001]: application `service`; infrastructure `k8s-cluster`, `database`, `queue`, `bucket`; network `vpc`, `landing-zone`, `transit-gateway`, `vpn`, `direct-connect`, `firewall`; external `on-prem-system`, `saas`; team `team`. Edge types are seeded as `depends_on`, `calls`, `runs_on`, `stores_data_in`, `routes_via` and `owned_by`. [BR-001]
- **SPEC-model-03** Each type has an attribute schema (a JSON Schema subset: string, number, boolean, enum, array of string; required flags). Writes whose `attributes` don't match the schema fail with `422` (`type: /problems/validation`), and the problem lists each bad field. The `calls` edge type is seeded with `protocol` (enum `http`, `https`, `grpc`, `tcp`, `amqp`, `kafka`, other) and `port` (number 1–65535). [BR-001] [BR-003]
- **SPEC-model-04** Each edge type declares which node kinds it may go from and to (for example `runs_on`: application → infrastructure; `routes_via`: application or edge path → network). A disallowed pair fails with `422`. [BR-001]
- **SPEC-model-05** A node is identified by `(environment, id)`. The `id` is a slug matching `^[a-z0-9][a-z0-9-]{1,62}$`, supplied by its author, unique within the environment and immutable. The `name` is free text and can change. [BR-002] [BR-011]
- **SPEC-model-06** Every node has an `environment` from the configured list (seeded with `dev`, `uat`, `prod`) and exactly one owner team (`owner`, a team id). [BR-002]
- **SPEC-model-07** An edge connects two nodes in the same environment, and is unique by `(environment, type, from, to)`. Edges across environments are not allowed in the MVP and fail with `422`. [BR-001] [BR-002]
- **SPEC-model-08** Every node and edge has a `source` (`ui`, `yaml`, `discovery` or `import`) recording the path that last wrote it. [BR-004]
- **SPEC-model-09** Deleting a node also deletes its edges in the same transaction, and both are recorded in the history ([ADR-0005]). Deleting a team or type that is still in use fails with `409` (`type: /problems/in-use`), and the problem gives a count of the dependents. [BR-001] [BR-003]
- **SPEC-model-10** No attribute may hold a secret. Any attribute whose name matches `(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)`, or any string value that looks like a credential (a URL with userinfo `user:pass@`, a PEM block, an AWS access key `AKIA…`), is rejected with `422` (`type: /problems/secret-detected`). [NFR-002]

## Interfaces

All under `/api/v1`, JSON, RFC 9457 errors, permissions per [SPEC-identity-access-05].

- `GET /types` → node and edge types with their attribute schemas and allowed kind pairs.
- `GET /teams` → teams.
- `GET /environments` → configured environments.
- `GET /nodes?environment=&kind=&type=&owner=&q=&limit=&cursor=` → a page of nodes (`q` matches id and name).
- `GET /nodes/{environment}/{id}` → a node.
- `GET /edges?environment=&type=&from=&to=&limit=&cursor=` → a page of edges.
- `GET /graph?environment=` → every node and edge in one environment, in a compact form for rendering ([NFR-005]).
- Writes are in [003_editing-history.md] and [004_yaml-as-code.md].

## Data

- `node_types(id, kind, name, attributes_schema jsonb, builtin bool)`
- `edge_types(id, name, attributes_schema jsonb, allowed jsonb, builtin bool)`
- `teams(id slug, name, created_at)`
- `environments(id slug, name, sort)`
- `nodes(environment, id, type, name, description, owner, attributes jsonb, tags text[], source, created_at, updated_at, version int)`, primary key `(environment, id)`
- `edges(uid uuid, environment, type, from_id, to_id, attributes jsonb, source, created_at, updated_at, version int)`, unique `(environment, type, from_id, to_id)`
- Migrations in `arch-api/migrations/` (goose); queries in sqlc ([ADR-0004]).

## Non-functional

- [NFR-005]: `GET /graph` for 2,000 nodes and 10,000 edges returns in under 1 s server-side, gzip on.
- `version` gives optimistic locking: writes send `If-Match`, and a mismatch returns `412`.

## Open questions

- Should cross-environment edges (for example a dev app calling a shared prod on-prem API) be allowed later? Out of scope for the MVP. — khajonpot

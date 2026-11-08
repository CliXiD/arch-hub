# Spec 003: editing-history

> Status: Draft · Implements: [BR-010], [BR-042], [NFR-003] · Decisions: [ADR-0016] (supersedes [ADR-0005]), [ADR-0007], [ADR-0014]
> Repos: arch-api, arch-web · Last reviewed: 2026-11-08

## Summary

Editors create, change and delete nodes and edges through forms in the UI. Every change, from
any path, is written to the append-only change log, and anyone can read a node's history.

## Behaviour

- **SPEC-editing-history-01** An editor can create a node from a form with these fields: environment, type (grouped by kind), id (slug, live-validated per [SPEC-model-05]), name, description, owner (limited to their own teams unless they are an admin), tags, and the type's attributes rendered from its schema. Validation errors from the API show next to their fields. [BR-010]
- **SPEC-editing-history-02** An editor can edit a node's name, description, owner, tags and attributes, but not its id, type or environment. If the node was last written by YAML (`source: yaml`), the form shows a warning: "This node is managed by YAML; your change will be overwritten by the next push." [BR-010] [BR-011]
- **SPEC-editing-history-03** An editor can add an edge from a node they can edit by choosing an edge type and a target node (searchable, limited to the kinds the type allows), then filling the edge's attributes. They can also edit and delete such edges. [BR-010]
- **SPEC-editing-history-04** Deleting a node asks for confirmation in the page (not a browser dialog) and states how many edges will be removed with it. [BR-010]
- **SPEC-editing-history-05** If someone else changed the item since the form was opened (`412`), the form says so and offers to reload, showing the newer values. [BR-010]
- **SPEC-editing-history-06** Every create, update and delete of a node, edge, type, team or environment writes one `change_log` row in the same transaction, with the actor, actor kind, source, and the before and after values. A failed write leaves no row. [BR-042] [NFR-003]
- **SPEC-editing-history-07** A node's History tab lists its changes and those of its edges, newest first, in pages of 50. Each entry shows when, who and what changed (a field diff), and its source. With no changes yet it shows "No changes recorded". [BR-042]
- **SPEC-editing-history-08** The API's database role has no `UPDATE` or `DELETE` grant on `change_log`, and a trigger rejects `UPDATE`, `DELETE` and `TRUNCATE` on it; migrations run as a separate owner role ([ADR-0014]). An integration test checks both. [NFR-003]

## Interfaces

- `POST /api/v1/nodes` → `201` node; `PATCH /api/v1/nodes/{environment}/{id}` (`If-Match: <version>`) → `200`; `DELETE /api/v1/nodes/{environment}/{id}` → `204`.
- `POST /api/v1/edges` → `201`; `PATCH /api/v1/edges/{uid}` (`If-Match`) → `200`; `DELETE /api/v1/edges/{uid}` → `204`.
- `GET /api/v1/history?entity=node&environment=&id=&limit=&cursor=` → change entries (including the node's edges).
- Errors: `401`, `403`, `404`, `409 /problems/conflict` (duplicate id or edge), `409 /problems/in-use` (deleting a team that owns nodes or an environment that holds nodes; the body adds an integer member `count`, the number of nodes), `412 /problems/stale` (including `*`, weak or malformed `If-Match`), `428 /problems/precondition-required` (no `If-Match` on node or edge PATCH/DELETE), `422 /problems/validation` or `/problems/secret-detected`.
- Writes return the entity's version in `ETag` (`"1"` on create). CORS allows the `If-Match` request header and exposes `ETag`, so the browser app can use them.

## Data

- `change_log(id bigserial, at timestamptz, actor text, actor_name text, actor_kind user|service, source, entity node|edge|type|team|environment, entity_key text, action create|update|delete, before jsonb, after jsonb)`, indexed by `(entity, entity_key, at desc, id desc)`. Kept forever ([NFR-003], [ADR-0016]).
- `entity_key` formats: node `<environment>/<id>`, edge `<uid>`, team `<id>`, environment `<id>`. `before`/`after` hold the entity's API JSON; `before` is null on create, `after` null on delete.
- A node's edge history uses two partial expression indexes `WHERE entity = 'edge'`: `((coalesce(after, before)->>'environment'), (coalesce(after, before)->>'from'), at desc, id desc)` and the same with `'to'`. An edge's environment, `from` and `to` never change, so `coalesce(after, before)` is stable.

## Non-functional

- Writes affect one entity and complete in under 300 ms p95.
- Forms meet [NFR-006]: labelled fields, errors announced, keyboard-only use.

## Open questions

- None.

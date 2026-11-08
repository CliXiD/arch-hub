# Spec 008: admin

> Status: Draft · Implements: [BR-003], [BR-041] · Decisions: [ADR-0008], [ADR-0005]
> Repos: arch-api, arch-web · Last reviewed: 2026-11-08

## Summary

Admins manage the vocabulary of the model (node and edge types and their attributes), the
teams and the environments. Users and roles live in Keycloak ([ADR-0008]).

## Behaviour

- **SPEC-admin-01** `/admin/types` lists node types (by kind) and edge types. An admin can create a type, edit its name and attribute schema with a form-based schema editor (field name, data type, enum values, required), and, for edge types, edit the allowed kind pairs. [BR-003]
- **SPEC-admin-02** Changing a type's schema is checked against existing data. If existing nodes or edges would fail the new schema (for example a new required field without a default), the save fails with `409` and the problem gives a count of the failing items. Adding optional fields always succeeds. [BR-003]
- **SPEC-admin-03** Built-in types ([SPEC-model-02]) can have attributes added but can't be deleted or renamed. A custom type can be deleted only when unused ([SPEC-model-09]). [BR-003]
- **SPEC-admin-04** `/admin/teams` lists teams with their node counts. An admin can create a team (id slug and name) and rename one. Deleting a team is allowed only when it owns no nodes. The page explains that team ids must match the Keycloak group names ([SPEC-identity-access-05]). [BR-041]
- **SPEC-admin-05** `/admin/environments` lets an admin add an environment, rename one and reorder them. An environment can be deleted only when it is empty. [BR-002] [BR-041]
- **SPEC-admin-06** Every admin change is in the change log ([SPEC-editing-history-06]), and a global audit page `/admin/audit` lists all changes with filters by actor, entity, source and date. [BR-042]
- **SPEC-admin-07** Non-admins don't see the Admin menu, and get a "You need the admin role" page if they open an admin URL. [BR-040]

## Interfaces

- `POST|PATCH|DELETE /api/v1/types/node[/{id}]`, `/api/v1/types/edge[/{id}]`, `/api/v1/teams[/{id}]`, `/api/v1/environments[/{id}]` (admin only).
- `GET /api/v1/history?actor=&entity=&source=&from=&to=` (viewer), the global audit query.

## Data

- `node_types`, `edge_types`, `teams` and `environments` per [002_model.md].

## Non-functional

- Validating a schema change against existing data completes in under 5 s for 10,000 items.

## Open questions

- None.

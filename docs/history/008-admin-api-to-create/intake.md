DECISION: ACCEPT
RISK: high
SURFACES: security
REPOS: arch-api, arch-web
RESCOPED: no

## Summary
- Accepted as written: admin-only create, edit and delete of node and edge types in `arch-api`, plus the `schema.d.ts` regeneration in `arch-web`.
- No migration is needed: `arch_app` already has DML on `node_types`/`edge_types` (migration 00005) and `change_log.entity` already allows `type` (00004).
- The team/environment admin writes in `model/write.go` give the exact pattern to follow (one transaction, `record()` row, `InUseError` with `count`).
- Risk is high because it writes the change_log, extends secret detection to attribute names at type level, and type schemas decide what every later node/edge write accepts.
- Two document details are left for the spec writer to settle and list under Docs impact (URL prefix in spec 008's Interfaces line, `entity_key` format for `type`).

## Scope
**arch-api**
- New admin-only operations under `/api/v1/admin/types`: `POST /node-types`, `POST /edge-types`, `PATCH /node-types/{id}`, `PATCH /edge-types/{id}`, `DELETE /node-types/{id}`, `DELETE /edge-types/{id}`, with the statuses and problem types in the issue's Contract. Non-admins get `403` through the existing minimum-role registration.
- Create validates the id against the table's check constraint (node types `^[a-z0-9][a-z0-9-]{1,62}$`, edge types `^[a-z][a-z0-9_]{1,62}$`, as in migration 00002), the kind against the fixed five, and `attributes_schema` against the documented subset ([SPEC-model-03]: `type: object`, `properties` of string/number/boolean/enum/array of string with optional `minimum`/`maximum`, `required`, `additionalProperties`); anything else is `422 /problems/validation` at the field path. Edge types also take `allowed` kind pairs.
- PATCH accepts `name`, `attributes_schema` and (edge types) `allowed`; `kind` and `id` are immutable. A schema change is checked against every existing node/edge of that type (and a removed allowed pair against existing edges): any item that would fail gives `409` with `count`. Adding optional attributes always succeeds.
- Built-in types (`builtin = true`): attributes can be added, but removing a declared attribute or deleting the type is `409`. The display `name` may change; the id never does.
- Deleting a custom type still referenced by nodes/edges gives `409 /problems/in-use` with `count`; unused gives `204`.
- Any property name in `attributes_schema` matching the secret-name rules of [SPEC-model-10] (reuse `secretName`/`secretNameToken` from `internal/model/secrets.go`) gives `422 /problems/secret-detected` naming only the field path.
- Each successful write records exactly one `change_log` row with `entity = type`, before/after holding the type's API JSON, in the same transaction; a failed write leaves none.
- Table-driven tests, README endpoint table, `make openapi` regeneration of `api/openapi.yaml`.

**arch-web**
- Regenerate `src/api/schema.d.ts` from the new `openapi.yaml` (`pnpm gen:api`); no UI change.

**Left out** (as the issue says): the `/admin/types` page, changing a type's kind, any change to the YAML schema.

**For the spec writer**
- Spec 008's Interfaces line still reads `POST|PATCH|DELETE /api/v1/types/node[/{id}]` while SPEC-admin-01 (updated for this issue) and the issue use `/api/v1/admin/types/...`. Follow the issue, and list the Interfaces line in `docs/specs/008_admin.md` under Docs impact.
- Neither [SPEC-editing-history-06] nor [ADR-0016] defines `entity_key` for entity `type`. Node and edge type ids can collide (both tables could hold `service`), so a prefixed key such as `node/<id>` and `edge/<id>` is needed; record the choice as a Docs impact on spec 003 and ADR-0016.
- Decide the problem `type` for the built-in `409` cases (Behaviour 4) where no `count` applies; `/problems/conflict` is the existing fit.

## Why
The team and environment admin writes in `repos/arch-api/internal/model/write.go` and `internal/httpapi/routes_write.go` already do admin-only, single-transaction writes with a `change_log` row and `InUseError{Count}`, so the type endpoints are a contained extension; `validateAttributes` in `validate.go` and the name rules in `secrets.go` cover the schema and secret checks. Migrations 00004 and 00005 already allow `entity = 'type'` and give `arch_app` DML on the type tables, so no migration is needed and nothing on the Always-escalate list changes. The change reaches `openapi.yaml`, so `arch-web` regenerates `schema.d.ts` in the same job per the cross-repo rules.

## Questions
None.

## Research
None.

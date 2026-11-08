# Spec 004: yaml-as-code

> Status: Draft · Implements: [BR-011], [BR-004], [BR-043], [NFR-002] · Decisions: [ADR-0006], [ADR-0008]
> Repos: arch-api · Last reviewed: 2026-11-08

## Summary

A team describes its slice of the model in YAML files kept in its own repo, then validates and
pushes them with the `arch` CLI, usually from CI. The API upserts the slice by stable id.
Any slice can be exported back to YAML.

## Behaviour

- **SPEC-yaml-as-code-01** The YAML format is defined by a JSON Schema (2020-12) in `arch-api/schema/arch.schema.json` and served at `GET /schema/arch.json`. A document has `version: 1`, `environment`, `owner` (team id), a list of `nodes` (`id`, `type`, `name`, optional `description`, `tags`, `attributes`) and a list of `edges` (`type`, `from`, `to`, optional `attributes`). [BR-011]
- **SPEC-yaml-as-code-02** `arch validate <files…>` checks the files against the schema offline, and with `--server`, also against the live types. It prints each error as `file:line: message` and exits 1 on any error. [BR-011]
- **SPEC-yaml-as-code-03** `arch push <files…>` sends the documents to `POST /api/v1/import`. The import is all or nothing: if any node or edge fails validation, permissions or the secret check ([SPEC-model-10]), nothing is written, and the response lists every error with its file, path and line. [BR-011] [NFR-002]
- **SPEC-yaml-as-code-04** An import upserts nodes by `(environment, id)` and edges by `(environment, type, from, to)`, and sets `source: yaml` on everything it writes. Writes that change nothing produce no history entries. [BR-011] [BR-004]
- **SPEC-yaml-as-code-05** With `--prune`, an import also deletes the nodes owned by the document's `owner` in that environment that have `source: yaml` and aren't in the document, and the edges from those nodes. Without `--prune`, nothing is deleted. The response always lists what was created, updated, unchanged and deleted. [BR-011]
- **SPEC-yaml-as-code-06** `--dry-run` (`?dry_run=true`) returns that same summary without writing anything. [BR-011]
- **SPEC-yaml-as-code-07** An edge may point to a node owned by another team, which must already exist in the model or appear in the same push. An import can only create or update nodes whose `owner` is one of the caller's teams (admins may use any team). [BR-011] [BR-040]
- **SPEC-yaml-as-code-08** CI authenticates with client credentials from `ARCH_CLIENT_ID` and `ARCH_CLIENT_SECRET` against `ARCH_ISSUER`, per [SPEC-identity-access-07]. People can also run `arch login` (device code flow). [BR-043]
- **SPEC-yaml-as-code-09** `arch export --environment <env> [--owner <team>]` and `GET /api/v1/export?environment=&owner=` return YAML that is valid against the schema and round-trips: importing it changes nothing. [BR-011]
- **SPEC-yaml-as-code-10** The `arch` binary is built from `arch-api/cmd/arch/` with the same validation package as the server, and released as binaries for linux, darwin and windows (amd64 and arm64). [BR-011]

## Interfaces

- `GET /schema/arch.json` (auth required, like everything except health).
- `POST /api/v1/import?dry_run=&prune=`, body `application/yaml` (one or more documents) → `200 { "created": [...], "updated": [...], "unchanged": n, "deleted": [...] }` or `422 { "errors": [{ "file", "path", "line", "message" }] }`.
- `GET /api/v1/export?environment=&owner=` → `application/yaml`.
- CLI: `arch validate | push [--prune] [--dry-run] | export | login | version`; env `ARCH_URL`, `ARCH_ISSUER`, `ARCH_CLIENT_ID`, `ARCH_CLIENT_SECRET`.

## Data

- No new tables; it writes `nodes`, `edges` and `change_log` per [002_model.md] and [003_editing-history.md].
- Body limit: 5 MB per push.

## Non-functional

- An import of 500 nodes and 2,000 edges completes in under 10 s, in one transaction.

## Open questions

- None.

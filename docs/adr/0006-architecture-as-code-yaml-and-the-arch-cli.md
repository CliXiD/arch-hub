# ADR-0006: Architecture as code (YAML) and the arch CLI

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-011], [BR-004], [BR-043], [NFR-002]

## Context

Teams describe their slice of the model as YAML in their own repos and push it from CI; the UI can
edit too ([BR-010], [BR-011]). There is no shared model repo ([ADR-0001]). Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **YAML in git is canonical; UI edits write PRs back** — reviewable everywhere, but needs git
   write access and conflict handling from day one.
2. **The database is canonical; YAML is imported (upsert by stable id) and exported** — simple;
   teams can still keep and review their YAML in their repos; git write-back can come later.

## Decision

Option 2. The YAML format is defined by a JSON Schema (2020-12) in `arch-api/schema/`, served at
`GET /schema/arch.json`. Import upserts by stable id and records `source: yaml` ([BR-004]); it
rejects fields that look like secrets ([NFR-002]). The `arch` CLI (`validate`, `push`, `export`)
is a second binary in `arch-api/cmd/arch/`, sharing the server's validation code, and is released
as binaries. CI pushes with a Keycloak service account ([ADR-0008], [BR-043]).

## Consequences

- A UI edit to a YAML-sourced node is overwritten by the next push of that YAML; the UI must
  show the node's source and warn.
- Whether stable ids are author-supplied or derived is an open question in the BRD.

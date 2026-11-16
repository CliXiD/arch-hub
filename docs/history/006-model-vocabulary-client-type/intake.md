DECISION: ACCEPT
RISK: high
SURFACES: none
REPOS: arch-api
RESCOPED: no

## Summary
- Accepted as written: one new goose migration in `arch-api` that widens the built-in vocabulary; no endpoint, shape or web change.
- The hub documents already record this change ([SPEC-model-02], [SPEC-model-03], [SPEC-model-04] cite issue #17), so issue and documents agree.
- The code confirms the migration is enough: kind pairs and attribute schemas are read from `edge_types` at write time, and the validator already handles `enum`, `minimum` and `maximum`.
- Risk is high only because it is a DB migration (Factory notes); it adds rows and JSON keys, drops or renames nothing.
- One reading the code forces: there is no `migrate down` command, so the Up/Down check runs goose directly in the integration test.

## Scope
**arch-api** — a new migration `00006_*.sql` (Up and Down), plus tests:

- `node_types` gains four built-in rows: `client` (external, "Client or actor"), `load-balancer` (network, "Load balancer / ingress"), `container-registry` (infrastructure, "Container registry"), `job` (application, "Job"). `GET /api/v1/types` lists them with `builtin: true`.
- `edge_types.allowed` for `calls` and `depends_on` gains the pair `external → application`, appended after the existing pairs. `POST /api/v1/edges` with `calls` or `depends_on` from a `client` node to an application returns `201`; `/graph` and impact queries carry the edge like any other.
- `edge_types.attributes_schema`: `calls.protocol` enum gains `postgres` and `otlp`; `calls` gains optional string `path`; `stores_data_in` gains optional `port` (number 1–65535) and `role` (string). `protocol: smtp` and `port: 70000` still fail with `422`.
- Down restores the exact previous rows and JSON values (delete the four types, remove the pair, put back the old schemas).
- Tests: update the `seeded vocabulary` assertions in `cmd/arch-api/integration_test.go` to the new vocabulary; add write cases for the acceptance criteria (client → application `calls` and `depends_on`, `otlp` + `path`, `stores_data_in` with `port` and `role`, the two `422`s); add an integration test that applies the migration, rolls back one step with goose's provider, and checks types and edge types equal the pre-#17 state. Existing nodes and edges stay valid; undeclared attributes stay accepted (no code change needed).

Left out, per the issue: no admin endpoints for types, no change to the hub's dogfood model, and no new `migrate down` CLI subcommand (the rollback test uses goose directly; a user-facing rollback command would be a separate decision).

## Why
`migrations/00003_model_seed.sql` is the only place the vocabulary lives, and `internal/model/write.go` / `validate.go` read `allowed` and `attributes_schema` from the `edge_types` rows on every write, so a data migration changes behaviour with no Go code change. `cmd/arch-api/integration_test.go` asserts the exact current type list and `calls` schema, so it must be updated in the same PR. `internal/db/migrate.go` only supports `up` and `status` (and `main_test.go` asserts `migrate down` is rejected), hence the test-only rollback.

## Questions
None.

## Research
None.

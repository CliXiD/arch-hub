ESCALATE

## Summary
- Round 2 applied feedback 1, which the user accepted: `routes_via` in `migrations/00003_model_seed.sql` now also allows network→application, network→external and infrastructure→network. The sample graph gains `direct-connect routes_via core-banking`, so it now has 7 nodes and 7 edges. Tests, the README and the job spec were updated to match (commit `7dd2588`).
- Round 2 has `GATE: PASS` in both repos, and all four reviews (code, security, contract, db) are `VERDICT: PASS` with no findings. `api/openapi.yaml` did not change, so the arch-web `schema.d.ts` from round 1 is still current. I regenerated it from the arch-api branch and it is byte-identical.
- The change stays inside intake's Scope and REPOS. The protected paths (`00001_baseline.sql`, `embed.go`, `.github`) are untouched, and arch-deploy has no change.
- The allowed kind pairs are no longer an open question, because the user confirmed them in feedback 1. The job still escalates under fixed rules: it adds schema migrations and a data seed that runs in prod, and it adds dependencies.

## Why
Every acceptance criterion is met, with convincing evidence. My spot checks agree: the `routes_via` pairs in 00003 match the spec table, the sample chain is complete in `internal/model/seed.go`, and the cross-repo check shows that regenerating `schema.d.ts` from arch-api's `openapi.yaml` gives the committed file. Still, the change adds the first real goose migrations, plus a seed that runs in prod, and new Go dependencies. Each of these must go to a human. Both repos are `auto_merge: false` in any case.

## Acceptance criteria
1. [arch-api] `00002`/`00003` are present; baseline, `embed.go` and `.github` are untouched: met. I checked this myself: the `git diff --stat` on those paths is empty.
2. [arch-api] `/types`: 14 node types and 6 edge types, the `calls` schema, `runs_on.allowed` exactly application→infrastructure: met. build.md shows the live check, and I read 00003 myself.
3. [arch-api] Environments come back as dev/uat/prod in order, and teams is empty: met (build.md live check on a throwaway DB).
4. [arch-api] `seed --sample` loads 7 nodes and 7 edges. The graph nodes have no `attributes`, and `calls` carries https/443: met (build.md live check after the round 2 reset, plus the integration test).
5. [arch-api] A second seed exits 1 and the node count stays 7: met (build.md live check and the integration test).
6. [arch-api] Following the cursors returns all 7 nodes once, ordered by id: met (build.md lists the ids over 4 pages).
7. [arch-api] `limit=501`, `cursor=zzz` and `environment=nope` give 422 `/problems/validation` with no `value`: met (build.md shows the body; unit tests cover it).
8. [arch-api] `ETag: "1"` and the expected body; an unknown node gives 404 `/problems/not-found`: met (build.md live check and unit tests).
9. [arch-api] The `routes_via` filter returns 4 edges and `q=PAY` returns only `payments-api`: met (build.md round 2 live check).
10. [arch-api] `/graph` is gzipped only when `Accept-Encoding` asks for it; a missing environment gives 422: met (build.md live check and unit tests).
11. [arch-api] All seven routes give 401 without a token, and the default-deny test passes: met (`TestModelRoutesNeedAToken`; the gate passed).
12. [arch-api] The integration test passes, including 2,000 nodes / 10,000 edges in under 1 s: met (build.md: 41 ms on podman). The test is outside the gate by design.
13. [arch-api] The sqlc output is current, and `openapi.yaml` has the 7 operationIds: met (build.md; `make openapi-check` passed in the gate).
14. [arch-api] `seed` and `seed --force` print the usage and exit 2: met (`TestRun`; build.md).
15. [arch-api] The README documents the seed, the endpoints, sqlc and the integration tests: met (build.md; code review).
16. [arch-web] `schema.d.ts` equals the regenerated file, and it is the only changed file: met. I checked this myself across repos: the regenerated file is identical, and `git diff --stat` lists only `src/api/schema.d.ts`.

## Merge order
1. CliXiD/arch-api#3 first. On deploy, the migrate job applies `00002` and `00003` before the new pods serve.
2. CliXiD/arch-web#3 after arch-api#3 has merged. If arch-api#3 changes before merge, rerun `pnpm gen:api` first. It only adds types, so it can deploy any time after arch-api.
3. arch-deploy: no change.

## Docs impact
- `docs/specs/002_model.md`:
  - [SPEC-model-04]: record the full default `allowed` pairs of the six edge types, including the extended `routes_via` set (application→network, network→network, network→application, network→external, infrastructure→network).
  - [SPEC-model-03]: note that the `calls` attributes are optional.
  - Data: note that `edge_types.id` is snake_case, that `kind` comes from `node_types` and is not stored on `nodes`, and that foreign keys do not cascade.
  - Interfaces: until a single-edge read exists, only `GET /nodes/{environment}/{id}` carries an `ETag`. Document the `422 /problems/validation` and `404 /problems/not-found` cases of the read endpoints.
- `docs/specs/009_operations.md` Interfaces: add `arch-api seed --sample`, a local-development command that refuses when any node exists.
- `AGENTS.md` (hub), Local services, "Run an app natively": add the optional `go run ./cmd/arch-api seed --sample` step after `migrate up`.

## For the human
All checks and reviews passed, and the `routes_via` change you asked for in feedback 1 is in. The PRs are ready to merge in the order above. Before you merge, please confirm two things:

1. **Schema migrations and prod seed.** Look at `migrations/00002_model.sql` and `migrations/00003_model_seed.sql` in CliXiD/arch-api#3.
   - `00002_model.sql` adds six new tables with non-cascading foreign keys and four indexes.
   - `00003_model_seed.sql` seeds 14 node types, 6 edge types with their allowed pairs, and the environments dev/uat/prod.
   - Both are additive and the db review found nothing wrong. They are the first real migrations, and they will run in prod. Once 00003 has run anywhere shared, any later change to the seeded pairs needs a new migration.
2. **New dependencies in `go.mod`.**
   - `github.com/gin-contrib/gzip` v1.2.10.
   - `github.com/google/uuid`: it was already an indirect dependency and is now direct.
   - `github.com/testcontainers/testcontainers-go` and its postgres module v0.45.0. Only the `integration` build tag uses them.
   - `github.com/sqlc-dev/sqlc` v1.31.1 as a `tool`.
   - There are many new indirect modules. The indirect `magiconair/properties` moved from 1.8.6 to 1.18.12.

Non-blocking follow-ups:
- The integration test (`cmd/arch-api/integration_test.go`) is not wired into CI, because `.github` is protected.
- `seed --sample` prints raw database errors on stderr, which can include the host, user and database name. `migrate` and `serve` already do the same.
- Keep `seed --sample` out of any prod job.
- Any local dev database that ran the round 1 version of 00003 needs `dev/bin/stack reset` to pick up the new pairs.

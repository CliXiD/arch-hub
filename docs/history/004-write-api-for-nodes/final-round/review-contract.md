VERDICT: PASS

## Summary
- arch-web's `src/api/schema.d.ts` is byte-identical to a fresh `openapi-typescript` run on the arch-api worktree's `api/openapi.yaml`, so the generated contract is in sync.
- The arch-web diff is only that generated file. No screens or callers change, which matches the spec.
- The change is additive: new operations, new problem types and a new table. The existing read shapes are unchanged, so the deployed web keeps working before regeneration.
- The migrations match the Contract. `00004` adds `change_log` and `00005` adds the `arch_app` grants. The old migrations are untouched. No new env var is needed.
- CORS now allows `If-Match` and exposes `ETag`, which a browser editor will need later.

## Findings
None.

## Notes
- Deploying `00005` needs role `arch_app` to exist first, as the spec says. The deploy repo is not in this job, so confirm the Helm migrate job has that role before rollout.
- The `/problems/in-use` response carries an extra `count` member. It is declared in the OpenAPI schema as `InUseProblem`, so the generated types include it.

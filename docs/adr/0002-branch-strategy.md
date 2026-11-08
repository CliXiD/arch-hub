# ADR-0002: Branch strategy

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot, /hub-init 2026-11-08
- Relates to: [BR-040]

## Context

A small team (the product owner plus the software factory) with no fixed release cadence and no
deadline. Source: decided in /hub-init on 2026-11-08.

## Options considered

1. **trunk** — feature branches from `main`, PRs into `main`. Simplest; fits continuous delivery.
2. **env** — env branches (dev, uat, pre) each feature is merged into in turn. Extra merges with
   no team or process that needs them.
3. **release** — semver release candidates each sprint. Needs a sprint cadence that doesn't exist.

## Decision

`trunk` in every repo. Feature branches start from `main` and PR into `main`. A job branch
catches up with `main` by **rebase**. `main` requires one approving PR review, so
`auto_merge` is off in every repo and the factory stops at "approved, waiting for a human merge".

## Consequences

- `factory/repos.json` → `branching`: `{"strategy": "trunk", "sync": "rebase"}`.
- Branch protection on `main` (1 review) must be set in each repo after it is created.
- Deploys to dev and prod are a person's call from `main` ([ADR-0009]).

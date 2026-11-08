# ADR-0015: Factory auto-merge

- Status: Accepted
- Date: 2026-11-08
- Deciders: khajonpot (via Discord, 2026-11-08)
- Relates to: [ADR-0002]

## Context

[ADR-0002] chose `trunk` and said `main` requires one approving review, so `auto_merge` was off
everywhere and every approved job stopped at "waiting for a human merge". The repos are private
on GitHub Free, where branch protection and rulesets are not available, so that review rule was
never enforced. Job 001 showed the human merge step adds a wait without adding a check the
approver and the gate don't already make. The product owner asked for the factory to commit,
open PRs and merge on its own, one at a time.

## Options considered

1. **Keep human merges everywhere** — safest; every job waits on a person, even routine ones.
2. **Auto-merge in the app repos, human merge for deploy, always-escalate list kept** — routine
   app jobs flow through; auth, audit, destructive migrations, new public endpoints, secret
   patterns and every `arch-deploy` change still go to a person.
3. **Auto-merge everything** — fastest; removes the only human check on high-risk changes.

## Decision

Option 2. This supersedes only the merge rule of [ADR-0002]; trunk, rebase and the rest stand.

- `auto_merge: true` for `arch-api` and `arch-web`; `arch-deploy` stays `false`.
- The approver keeps escalating everything on the AGENTS.md **Always escalate** list; auto-merge
  applies only to jobs it approves.
- Merges happen one job at a time (`concurrency: 1`), through `factory/bin/job merge`: each
  branch is rebased on `main`, gated again, and the PRs merge in `merge_order`. Any failure stops
  the job at `needs-human`.

## Consequences

- `factory/repos.json`: `auto_merge` true for `arch-api` and `arch-web`.
- AGENTS.md cross-repo rules no longer say every PR is merged by a human.
- Hub changes (`docs/history/`, docs edits) are still committed by a person or on request.
- If the repos later move to a plan with branch protection, a required review would block
  auto-merge; revisit this ADR then.

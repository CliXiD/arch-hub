---
name: hub-onboard
description: Make a new hub ready for the factory. Turns the check-script drafts that factory/bin/add-repo generated into checks that pass on each repo's base branch, settles repos.json (roles, merge order, protected paths, auto-merge, cross-repo rules), and fills AGENTS.md's system map, cross-repo rules and Factory notes with the user. Use when the user types /hub-onboard, just created a hub or added a repo, or factory/bin/setup reports checks with to-do markers or failures.
disable-model-invocation: true
---

# Onboard the hub

Goal: `factory/bin/setup --checks` passes for every repo, `factory/repos.json`
is right, and `AGENTS.md` tells every factory agent what it needs to know. You
change only hub files (`factory/`, `AGENTS.md`, `dev/env/`); you never change,
commit or push anything inside `repos/`.

Run it after `/hub-init` (which adds or creates the repos and writes the BRD,
specs and ADRs), and again whenever a repo is added or a new project's repo gets
its first code. Read `docs/adr/` first: the ADRs say which stack each repo uses
and how it is built, so the checks must match them. If `factory/repos.json` has no
repos yet, stop and point the user to `/hub-init` (or `factory/bin/add-repo`).

An argument may name repo keys to onboard; otherwise do every repo in
`factory/repos.json`. Keep a task list: one item per repo, then repos.json,
then AGENTS.md, then the final `setup --checks`.

## 1. Inventory (facts are yours)

Read `factory/repos.json`, then for each repo `factory/onboarding/<key>.md`
(what add-repo detected: stack, scripts, CI commands, services, env). If a
report is missing or stale, run `factory/bin/add-repo --redetect <key>`.

For each repo, dispatch an `Explore` sub-agent (in parallel) to answer, with
file paths:

- What does CI run (workflow files), in which order, with which runtime
  versions, and which steps need services (databases, browsers, docker)?
- Which test commands are unit-only, and which need services (e2e,
  integration, Playwright)? How do they select tests (paths, markers, configs)?
- The runtime version pins (.nvmrc, .python-version, go.mod, toolchains), the
  package manager and lockfile, and any `engines` / engine-strict settings.
- Build-time env vars the build needs (static env imports, config validation
  at build time) and the env example file.
- Where schema migrations live, generated code, CI config: candidates for
  `protected_paths` (existing files the factory must never edit).
- Its role in one line, and which other repos it calls or is called by.

Never read real `.env` files; examples only.

## 2. Make each repo's checks pass

`factory/checks/<key>.sh` is a draft. Make it mirror the repo's CI for lint,
typecheck, unit tests and build, using the libraries in `factory/checks/lib/`
(`common.sh`: `step`, `hub_env`; `node.sh`: `node_setup`, `pm`; `python.sh`:
`python_setup`). Rules:

- Unit tests only. Anything that needs services stays out of the gate and goes
  into the onboarding report's "needs services" list for `/hub-dev-stack`.
- One-shot and non-interactive: no watch mode, no prompts, `CI=true` is set.
- Never rewrite tracked files (no `--fix`, no formatters in write mode).
- Pin the runtime the repo pins (the libs handle .nvmrc via fnm/nvm).
- If the build needs env vars, write `dev/env/<key>.env` with local dummy
  values (copy key names from the example, never values from a real `.env`),
  set `env.target` in repos.json, and call `hub_env` before the build.
- Remove every `FACTORY-TODO` line you resolve; `factory/bin/setup` flags scripts that still have one.

Run it the way the gate does, on a clean worktree of the base branch:

```bash
factory/bin/setup --checks          # all repos; logs in .worktrees/_setup/<key>.log
```

Read the log tail of each failure and classify it:

- **Our script is wrong** (wrong command, missing setup, wrong runtime, env):
  fix the script and run again.
- **The environment is missing something** (a runtime version, a tool): tell the
  user the one install command, then run again.
- **The repo's base branch is broken** (tests that fail on the base branch for
  reasons unrelated to our setup): don't fix the repo. Show the user the
  failing tests and the cause you found, and say every job touching this repo
  will fail the gate until it's fixed upstream; offer to grill it into a hub
  issue with `/grill-issue`.

Iterate until every repo passes or is waiting on an upstream fix.

## 3. Settle repos.json

Show the user, in one grilling round (call the Skill tool with "grilling" for
the format: numbered questions, recommended answers, "yes" accepts), what you
propose and why:

- `role` for each repo (one line; intake and the spec writer read it).
- `base` per repo: the branch feature branches start from (normally `main`).
  Where PRs go is `branching` (top of `factory/repos.json`, set by `/hub-init`
  with the Branch strategy ADR): `trunk` → the base, `env` → each env branch in
  turn, `release` → the current rc. If `branching` is missing, ask the Branch
  strategy questions from `/hub-init` (Phase 3) before going on.
- `merge_order`: providers before callers (schema → API → frontends → deploy).
- `protected_paths` per repo: existing migrations, CI config, generated code.
- `auto_merge`: `false` (the default) when branch rulesets require human reviews,
  for schema-only, deploy and infra repos, and for any repo merged by hand: the
  factory then stops at "approved, waiting for a human merge" and notices the
  merge itself. `true` only where the factory may merge with no human review.
- `implies`: `db` for repos that own schema, `infra` for deploy repos.
- `rules`: pairs where a new file in one repo needs a new file in another (a
  migration and its mirror, an OpenAPI spec and its generated client), in the
  format documented at the top of `factory/bin/gate`.

Write what they accept. Then run `factory/bin/add-repo --redetect <key>` for
each repo so the docs, workspace and issue template pick up the changes (it
keeps the check scripts).

## 4. Fill AGENTS.md

`/hub-init` normally fills these from the BRD and ADRs; complete or correct what
is missing, citing the documents (`see [ADR-0003]`). If something in the code
contradicts an ADR, don't edit the ADR: tell the user and offer a superseding one.
Replace every TODO in `AGENTS.md` (keep the generated `hub:repos` block):

- **How the pieces connect**: who calls whom and over what, where the schema
  lives, what deploys what. A small ASCII diagram from what Explore found.
- **Cross-repo rules**: keep the defaults, add the project's own (where schema
  changes start, mirrored repos, shared packages, generated clients).
- **Factory notes**: grill the user for these in one or two rounds; recommend
  answers from what you found in the code:
  domain, language, high-risk areas, sensitive data, always-escalate list,
  conventions (commit style, test style, generators), grill checklist.

## 5. Finish

Run `factory/bin/setup --checks` once more and show the result per repo. Then
summarise what changed in the hub (files), what still waits on someone (upstream
fixes, installs), and the next steps: `/hub-dev-stack`, commit the hub, then
`/grill-issue` for the first requirement. Don't commit or push; the user does.

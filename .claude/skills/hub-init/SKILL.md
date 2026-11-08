---
name: hub-init
description: First-time setup of a hub's knowledge. Asks what the hub is for (a new project, or a hub for a system that already exists), gathers the sources to read (pasted briefs, wiki, web, Confluence, Jira, Google Drive, files), and with the user turns them into the hub's documents in grill-me style - a BRD, specs and ADRs that cite snapshots of their sources - then brings in or creates the source repos and fills AGENTS.md, so the factory's orchestrator can work from the hub alone. Use when the user types /hub-init, just ran bin/new-hub, or asks to set up, bootstrap or document a hub.
disable-model-invocation: true
---

# Initialise the hub

When you're done, someone who has only the hub folder can understand the project:

```
docs/brd.md              why, for whom, what (BR-xxx, NFR-xxx), every item citing a source
docs/specs/NNN_<area>.md how each area behaves, numbered in reading order (SPEC-<area>-xx)
docs/adr/NNNN-*.md       every stack and architecture decision, with options and reasons
docs/sources/            a snapshot of every source, with its link and hash, for /docs-sync
factory/repos.json       every source repo, cloned under repos/ (or created from the hub)
AGENTS.md                system map, cross-repo rules, Factory notes
```

Read `docs/README.md` (conventions, IDs, order of trust) and `factory/hub.json` first.
This is long work over several sessions: keep a task list, and record progress in
`factory/onboarding/hub-init.md` (phase, what's settled, what's open) after every phase,
so a later `/hub-init` resumes where this one stopped. If that file exists, read it and
continue from there.

**How you ask.** Call the Skill tool with "grilling" and follow it in every phase:
rounds of numbered questions, a recommended answer for each, "yes" accepts it. Ask in
the language `factory/hub.json` or the user uses. **Facts are yours**: anything a source
or the code can answer, look up with sub-agents (`researcher`, `Explore`) instead of
asking. **Decisions are the user's.**

**Never**: commit or push (the user does), create GitHub repos without an explicit
yes for that list, read real `.env` files, put secrets or real personal data in docs.

## Phase 0 — Goal

Round 1, whatever the mode:

1. **Mode**: a *new project* (nothing built yet) or a hub for an *existing system*
   (repos already exist)? Recommend from `factory/hub.json` `mode` and whether
   `repos/` has anything.
2. **Purpose**: the project in two or three sentences: the problem, for whom, the outcome.
3. **People**: the users and stakeholders, and who decides on business rules.
4. **Sources**: everything you should read, and where it lives:
   - text they paste now (a brief, a prompt, meeting notes)
   - links: wiki, internet pages, Confluence pages or spaces, Jira epics, Google Drive
   - files they can attach or put in the hub
5. **Language** for the documents, and the docs owner.

Write `mode`, `purpose` and `language` into `factory/hub.json`.

## Phase 1 — Sources (both modes)

For every source the user named:

- Pasted text: save it to a temp file, `factory/bin/docs add-source --kind prompt
  --ref "prompt:<date> <short name>" --title "<name>"`, then
  `factory/bin/docs record <S-id> <file>`.
- Everything else: dispatch `researcher` agents (Job A, a few sources each, in
  parallel) with the hub path, the kind, the link and a title. They register the
  source, snapshot it and summarise it.

Show a table: S-id, title, kind, state, one-line summary. For each `unreachable` source,
say what would fix it (connect the Atlassian or Google Drive connector, attach the file,
add the domain to `factory/config.json` → `research`) and ask whether to wait or go on.
Read the snapshots (have `Explore` summarise very long ones by section, with headings).

## Phase 2 — Understand

### New project

Grill the BRD into shape. Seed the design tree with: problem and background, goals and
how they are measured, users and their journeys, scope and out of scope, business
requirements (Must / Should / Could), non-functional requirements (security and privacy
law, availability, performance, data retention, audit, languages, accessibility),
integrations with other systems, data the system owns, constraints (budget, deadlines,
regulation), and open questions. Recommend every answer from the sources and cite them
(`per [S-002]`); ask only what the sources don't settle.

### Existing system

1. **Repos.** Ask for every repo of the system: git URL, the base branch the hub works
   from (when not given, `main` is the baseline; if a repo has no `main`, use its default
   branch and say so), and a one-line role. Ask how changes flow between branches
   (feature → dev → uat → pre → main, or straight to main) and which branch factory PRs
   should target; recommend the branch feature PRs target today.
2. **Clone** (confirm the list first), one at a time:
   `factory/bin/add-repo <url> --key <key> --base <branch> --role "<role>"`.
3. **Read the code.** Dispatch one `Explore` sub-agent per repo, in parallel, for:
   purpose and modules; interfaces (endpoints, events, screens, jobs) with file paths;
   the data model and where migrations live; integrations with other repos and outside
   systems; auth and permissions; config and env vars; how it's built, tested and
   deployed; the stack with versions (languages, frameworks, libraries, databases,
   infrastructure). Then one more for how the repos connect.
4. **Grill the BRD** as for a new project, but recommend answers from what the code
   does today and the sources. The code shows *what*; ask the user *why* and for whom.

## Phase 3 — Stack and architecture → ADRs

### New project

Ask whether the organisation has a baseline stack or architecture standard (a Confluence
page, a wiki, a document). If so, snapshot it as a source and recommend from it. Then
grill the stack, recommending answers that fit the BRD and the baseline:

- architecture style (one service or several), and **which repos** to create (key,
  name, purpose), the branch flow and base branch for each
- languages, frameworks and versions per repo; API style; frontend and mobile
- database, migrations tool, cache, queues or streams, file storage, search
- identity and auth, secrets management
- hosting and deploy (containers, Kubernetes, GitOps, environments), CI
- observability (logs, metrics, tracing), testing strategy, local development

Each settled decision becomes an ADR: `factory/bin/docs adr-new "<title>"`, then fill
Context (cite BRD items and sources), Options considered (the ones you discussed),
Decision, Consequences, `Status: Accepted`, `Deciders: <user>, /hub-init <date>`.

### Existing system

Write the as-built ADRs from what Explore found, one per significant decision
(framework per repo, database and migrations, auth, messaging, deploy, frontend, ...):
`Status: Accepted (as-built)`, Context citing `<key>:path` and sources, Options
considered `Not recorded` unless the user or a source says. Show the list in one round
and ask the user to confirm each and add the reasons they know ("yes" keeps it as written).

### Branch strategy (both modes)

Grill how code moves to production, and write it as an ADR ("Branch strategy")
plus `factory/repos.json` → `branching`. Existing system: recommend what the
repos' branches and merged PRs show (`git branch -r`, `gh pr list --state merged`);
new project: recommend from the delivery cadence in the BRD.

1. **Strategy**:
   - `trunk` — feature branches from `main`, PRs into `main`.
   - `env` — environment branches (e.g. `dev`, `uat`, `pre`): feature branches
     start from `main`, and the same feature branch is merged into each env in
     turn, then into `main`. Env branches are never merged into each other or
     into feature branches.
   - `release` — semver release candidates: `release/<x.y.z>-rc.<n>` cut from
     `main` each sprint; feature branches start from `main` and PR into the
     current rc. To pull a feature out, cut `rc.<n+1>` from `main` and re-merge
     the rest; the rc ships by merging into `main` (tag `v<x.y.z>`). Features
     that missed the release are rebased onto the new `main`.
2. **Base** branch per repo (where feature branches start): `main` unless a repo
   differs.
3. For `env`: the env branches in promotion order, whether each exists in every
   repo (create missing ones from `main` only with a yes:
   `git -C repos/<dir> push origin origin/main:refs/heads/<env>`), and who
   promotes (always a person's call; the factory opens the PRs on request).
4. For `release`: the branch prefix (`release/`), version scheme (semver), rc
   numbering, whether the factory tags `v<x.y.z>` on ship, and when the first
   rc is cut (`factory/bin/job release cut <x.y.z>` — the factory can't target a
   release until one exists).
5. How a job branch catches up with the base: `merge`, or `rebase` (the default
   for `release`, since branches must sit on top of the latest `main`).
6. Branch protection: which branches need PR reviews. With required reviews,
   keep `auto_merge` off: the factory stops at "approved, waiting for a merge".

Write `branching` as:
`{"strategy": "env", "envs": ["dev", "uat", "pre"], "release_prefix": "release/",
"release_current": null, "sync": null}` (`sync` null = rebase for release, merge
otherwise), and the ADR with the options considered.

## Phase 4 — BRD and specs

- **BRD**: copy `docs/_templates/brd.md` to `docs/brd.md` and fill it from Phases 2-3.
  Every BR and NFR cites a source or says `Source: decided in /hub-init <date>`.
- **Specs**: one file per area (a bounded context, a user journey or a major screen
  group), numbered in reading order: `factory/bin/docs spec-new "<area>"` creates
  `docs/specs/NNN_<area>.md` from `docs/_templates/spec.md`. Order them so each spec only
  builds on earlier ones: the flows everything else depends on first (sign-up, identity,
  the core entity), then in the BRD's order, admin and back-office last. Agree the order
  with the user with the outline, and run `factory/bin/docs index` after writing them. New project: `Status: Draft`, from the BRD and
  ADRs. Existing system: `Status: As-built`, from the code, with each interface linking
  the files that implement it. Every spec lists what it implements (`[BR-xxx]`) and the
  ADRs it follows.

Show the outline (BRD sections with item counts, spec files with their items) and the
first spec in full; write the rest when the user agrees. Then `factory/bin/docs check`
and fix every error.

## Phase 5 — Repos and hub config

### New project: create the repos from the hub

Show the repo plan from Phase 3 (key, `owner/name`, visibility, base branch, role, the
ADRs it follows). On an explicit yes, for each:

```bash
factory/bin/add-repo --create <owner/name> --key <key> --base <branch> --role "<role>" --yes [--private] [--template <owner/template-repo>]
```

The repos start empty (or from the org template). Their check scripts are placeholders
until code exists; say that the first factory issues should scaffold each repo per its
ADRs (offer to grill those with `/grill-issue`: one walking-skeleton slice per repo).

### Both modes

- `factory/repos.json`: `merge_order` (providers before callers), `protected_paths`,
  `implies` (`db` for schema owners, `infra` for deploy repos), cross-repo `rules`, and
  `auto_merge` (leave it `false` when branch rulesets require human reviews: the
  factory then stops at "approved, waiting for a human merge"). Re-run
  `factory/bin/add-repo --redetect <key>` after edits.
- `AGENTS.md`: **How the pieces connect** (from the ADRs and code), **Cross-repo rules**
  (schema changes, branch flow, shared contracts), **Factory notes** (domain and
  language from the BRD; high-risk areas, sensitive data and always-escalate from the
  NFRs; conventions from the code; a grill checklist from the BRD's recurring concerns).
  Point each to the document it comes from (`see [NFR-003]`).

## Phase 6 — Finish

Run `factory/bin/docs check` and `factory/bin/docs list`. Update
`factory/onboarding/hub-init.md` to "done", and give the user:

- what was written (documents with item counts, repos added or created)
- open questions left in the BRD and specs, with owners
- next steps: commit the hub; `/hub-onboard` (checks per repo; existing system now,
  new project once code exists); `/hub-dev-stack` (works from the ADRs even before code
  exists); `/grill-issue` for the first requirement; `/docs-sync` whenever a source may
  have changed (or as a weekly scheduled task).

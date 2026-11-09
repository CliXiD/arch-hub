# Architecture E2E — workspace hub

One place to work on the project's repos together, by hand or through the software
factory. Created from the grill-me-factory template.

## Architecture

The product as built and deployed in `prod`, modelled in Architecture E2E itself through its
own API and drawn from `GET /api/v1/graph`. How it was made, how to regenerate it and what the
dogfooding turned up: [docs/architecture/README.md](docs/architecture/README.md).

![Architecture E2E architecture](docs/architecture/architecture.svg)

## Daily use

- Open `architecture-e2e.code-workspace` in VS Code (File → Open Workspace from File…).
- Run Claude Code from this folder so it sees every repo and the hub instructions (`AGENTS.md`, which `CLAUDE.md` imports).
- GitHub Copilot works from the same folder: it reads `AGENTS.md`, `.github/skills/` and `.github/agents/` (see below).
- Add a repo: `factory/bin/add-repo <git-url> [--key api] [--base main] [--role "..."]`.

## First-time setup

```bash
factory/bin/setup              # tools, hub remote, labels, repos
```

Then in Claude Code, from this folder:

1. `/hub-init` — asks whether this is a **new project** or an **existing system**, collects
   the sources to read (pasted brief, wiki, web, Confluence, Jira, Drive, files) and snapshots
   them into `docs/sources/`, then works with you, grill-me style, to write `docs/brd.md`,
   `docs/specs/` and `docs/adr/`. New project: it settles the tech stack (from your
   organisation's baseline if there is one) as ADRs and creates the repos from the hub.
   Existing system: it asks for the repos and base branches (default `main`), clones them,
   reads the code and writes as-built ADRs, specs and the BRD.
2. `/hub-onboard` — turns the generated `factory/checks/<key>.sh` drafts into checks that
   pass on each base branch, and settles `factory/repos.json` and `AGENTS.md` with you.
3. `/hub-dev-stack` — writes `dev/compose.yaml` and `dev/env/<key>.env` for the services the
   ADRs and repos need (podman first).
4. `factory/bin/setup --checks` — every repo's checks must pass on its base branch.

## Project documents

`docs/` is the source of truth for every agent: BRD, specs, ADRs, and snapshots of the
sources they came from, each with its original link. `/docs-sync` re-reads the sources,
shows what changed and which items cite them, and updates the documents with your
approval (`/docs-sync --jobs` folds in what merged factory jobs changed).
`factory/bin/docs check` validates IDs and citations. See `docs/README.md`.

## Local services

```bash
dev/bin/apply-env              # copy dev/env/<key>.env into each repo (never overwrites yours)
dev/bin/stack up [profile ...] # start the services; dev/bin/stack profiles lists the profiles
dev/bin/stack down | reset | ps | logs [service]
```

## Designing a requirement

`/grill-issue <idea, ticket or notes>` interviews you until every decision is settled, then
writes hub issues in the factory template and creates them only when you say so.

## Software factory

```
hub issue labeled `factory`
  → intake (fable)      accept / ask / reject; REPOS, risk, surfaces
  → route (script)      reviewers: code + ux/ui + security + db + infra + contract (multi-repo)
  → worktrees           .worktrees/<job>/<repo>/ on factory/<job> in every repo
  → spec-writer (opus)  spec.md with the cross-repo Contract and merge order
  → builder (opus)      commits + one draft PR per changed repo ("Part of <hub>#n")
  → gate (script)       each repo's checks, protected paths, cross-repo rules
  → reviewers           in parallel; CHANGES → builder → gate → reviewers (max 3 rounds)
  → approver (opus)     APPROVE → merge PRs in merge order, close the hub issue
                        ESCALATE → PRs ready, decision on the hub issue, factory:needs-human
```

```
/factory run          drain the queue (concurrency in factory/config.json, default 1)
/factory run <n>      one hub issue
/factory <anything>   ask about jobs, give feedback, file a requirement
```

Repos with `auto_merge: false` (the default) are never merged by the factory: approved jobs
wait in **Ship** for you to merge their PRs in order. An issue whose `## Blocked by` lists an
open issue waits.

Branch strategy (`factory/repos.json` → `branching`, decided in `/hub-init`): feature branches
always start from `main`.

```
trunk    PR → main
env      PR → dev, then  /factory promote #12  → uat → pre → main   (job promote <id> [<env>])
release  PR → release/<x.y.z>-rc.<n>
         factory/bin/job release cut 1.4.0          new rc from main; dropped jobs rejoin
         factory/bin/job release drop <job>...      rc.<n+1> from main without those jobs
         factory/bin/job release ship --tag         after the rc is merged into main: close, tag, rebase leftovers
```

Dashboard: `factory/bin/serve`, then open <http://localhost:8000/> (board) and
<http://localhost:8000/history> (finished jobs). It serves only `factory/` and `docs/` on
127.0.0.1, never `repos/` or any `.env`; `--port` changes the port.

## GitHub Copilot

`AGENTS.md` holds the hub's instructions for every agent; `CLAUDE.md` only imports it. The
skills and agents are written once, for Claude Code, in `.claude/`, and mirrored for Copilot:

```bash
factory/bin/copilot-sync          # .claude/skills → .github/skills, .claude/agents → .github/agents/*.agent.md
factory/bin/copilot-sync --check  # exit 1 when the mirrors are stale (setup reports it too)
```

`new-hub` runs it once. Run it again (and commit `.github/`) whenever you change `.claude/`;
never edit the mirrors. In Copilot Chat (agent mode) use `/hub-init`, `/grill-issue`,
`/docs-sync`, ... and the custom agents (intake, researcher, reviewers, ...). `/factory run`
is Claude Code only; from Copilot use the `factory/bin/job` commands.

## Job history

When a job is merged or rejected, `factory/bin/job` copies its record (issue, intake, spec,
research, build, decision, final checks and reviews, PRs and head commits) into
`docs/history/<job-id>/` and updates `docs/history/README.md`. Commit it with the hub: it keeps
the why of every change in git, readable by people and AI without GitHub. Every commit in the
repos ends with `Factory-Job: <job-id>`, which points there. `factory/bin/job archive --all`
archives jobs that finished before this existed.

`factory/history.html` (the **history →** link on the board, or **record** on a finished card)
lists the records newest first with search across issue, spec and decision, filters by outcome
and repo, and opens each job's files in reading order; `history.html#<job-id>` links to one.

## Files

```
.claude/skills/        hub-init, hub-onboard, hub-dev-stack, docs-sync, grill-issue, grilling, grill-me, factory
.claude/agents/        researcher, intake, spec-writer, builder, approver, reviewer-{code,contract,security,db,infra,ux,ui}
.github/skills/, .github/agents/   Copilot mirrors of .claude/ (factory/bin/copilot-sync; don't edit)
AGENTS.md, CLAUDE.md   hub instructions for every agent; CLAUDE.md is just @AGENTS.md
docs/                  brd.md, specs/, adr/, sources/ (registry + snapshots), history/ (finished jobs), _templates/
factory/config.json    concurrency, rounds, labels, routing, prices
factory/repos.json     repos, bases, checks, protected paths, env, auto_merge, merge_order, rules
factory/checks/        <key>.sh per repo + lib/ (common, node, python)
factory/onboarding/    what add-repo detected in each repo
factory/bin/           add-repo, docs, job, gate, route, setup, serve, copilot-sync
factory/*.html         dashboard (live board), history (finished jobs from docs/history/)
factory/hub.json       the hub's mode (new | existing), purpose, language
dev/                   compose.yaml, env/, bin/stack, bin/apply-env
```

The factory is a multi-repo port of zazencodes' software-factory-claude-code-v2 (GPLv3,
`factory/LICENSE`); grilling and grill-me come from mattpocock/skills (MIT).

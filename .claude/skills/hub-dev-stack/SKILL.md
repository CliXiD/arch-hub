---
name: hub-dev-stack
description: Build the hub's local dev stack. Inventories the services every repo needs (databases, caches, queues, object storage, mail, third-party APIs to mock) and writes dev/compose.yaml (podman-friendly, with profiles per app) and dev/env/<key>.env with local dummy values, so each repo can run and run its e2e tests locally. Use when the user types /hub-dev-stack, asks for docker-compose/podman setup or .env files for the hub's repos, or a repo can't start without services.
disable-model-invocation: true
---

# Local dev stack

Goal: `dev/bin/stack up <profile>` brings up everything a repo needs, and
`dev/bin/apply-env <key>` gives the repo an env file that points at it. You
write only hub files: `dev/compose.yaml`, `dev/env/<key>.env`, `dev/<key>/`
helper scripts, `factory/repos.json` (`env`), and the Local services section
of `AGENTS.md`. Never change, commit or push anything inside `repos/`, and
never read real `.env` files (examples only).

An argument may name repo keys; otherwise cover every repo in `factory/repos.json`.

## 1. Inventory (facts are yours)

Read the ADRs in `docs/adr/` first: they name the databases, caches, queues,
storage, identity provider and third-party systems the project uses, with
versions. For a new project whose repos have no code yet, build the stack from the
ADRs alone and mark each service with the ADR it comes from (a comment in
compose.yaml).

Then start from `factory/onboarding/<key>.md` ("Services the code seems to use",
compose files, env keys). Then dispatch an `Explore` sub-agent per repo, in
parallel, to find, with file paths:

- Every env var the code reads and whether it is required (config validators,
  schema files, `process.env` / `os.environ` / `@Value` reads), grouped by
  service. Compare with the env example; list keys missing from it.
- The services behind them: database engine and version, cache, queue/stream,
  object storage, mail, search, auth provider, third-party HTTP APIs.
- What the repo's own compose files, Dockerfiles, CI service containers and
  test setup use (images, versions, init scripts, seed data).
- How the schema gets created (migrations command, seeds) and how the app
  starts in dev.
- Existing mocks for third-party APIs anywhere in the hub's repos (WireMock
  mappings, MSW handlers, fixtures) that a mock server could serve.
- Ports each app listens on, and how callers find it (API base URL vars).

## 2. Agree the stack with the user

One grilling round (call the Skill tool with "grilling" for the format):
the service list with images and ports, which apps get a container profile
(apps other repos call, so their callers can run against them), which
third-party APIs are mocked and how, and anything that can't run locally.
Recommend answers; "yes" accepts.

## 3. Write it

**`dev/compose.yaml`** (keep the header comment):

- Fully qualified, pinned images (`docker.io/library/postgres:17.6-alpine`) so
  podman pulls without short-name prompts; match the versions the repos use.
- Healthchecks on stateful services; named volumes for data.
- Services every repo needs have no profile. Each app container gets
  `profiles: ["<key>"]`, runs from `${<KEY>_DIR:-../repos/<path>}` (so a factory
  worktree can be run instead), keeps dependencies in a named volume
  (node_modules, .venv), uses `env_file: env/<key>.env` plus `environment:`
  overrides that swap `localhost` for service names, and has an entry script in
  `dev/<key>/` that installs, migrates, seeds and starts in dev mode.
- Two listeners where a broker needs them (host `localhost:<port>` for apps on
  the machine, an internal one for containers).
- Mount the repos' own init scripts and mock mappings read-only rather than
  copying them.
- Local dummy credentials only.

**`dev/env/<key>.env`** for each repo that reads env: every key the code
requires, with values that point at the stack on `localhost`, matching shared
secrets between repos (a JWT secret the API signs with and the admin app
verifies, an API key a caller sends), mocks for third-party endpoints, and
features that need real infrastructure switched off. Comment each group. Then
set `env` in `factory/repos.json`: `{"example": "<example file>", "target":
".env"}` (`.env.local` for Next.js).

## 4. Verify

- `podman compose -f dev/compose.yaml config` (or `docker compose ... config`)
  must parse. If no compose provider is installed, say so.
- Ask before starting containers (it pulls images). If the user agrees:
  `dev/bin/stack up` then each profile, watch `dev/bin/stack logs <service>`,
  and check each app answers on its port. Fix what fails.
- `dev/bin/apply-env` must report `wrote` or `same` for each repo.

## 5. Document

Replace the Local services section of `AGENTS.md`: the commands, the service
list with ports and dummy credentials, the profiles, how to run each app
against the stack (natively, or as a container profile), and `<KEY>_DIR` for
worktrees. Keep it short; agents read it before they start servers.

Finish with what was written, what was verified, and what the user still has
to do (install podman-compose, `podman machine init`, values that can't be
dummies). Don't commit; the user does.

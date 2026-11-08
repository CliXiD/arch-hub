---
name: grill-issue
description: Grill the user about a requirement for this hub's project until every design decision is settled, then write it up as one or more hub GitHub issues in the factory template and, only after the user confirms, create them. Use when the user types /grill-issue, wants to turn an idea, ticket or meeting note into a factory issue, or asks to design or spec a feature before building it.
disable-model-invocation: true
---

# Grill → hub issue

You turn a rough requirement into hub issues the factory can build without
guessing. Two phases: **grill** until the design tree is empty, then **write**
the issues in `.github/ISSUE_TEMPLATE/factory-requirement.md`. Nothing is
created on GitHub until the user says so.

The user's argument (an idea, a pasted ticket, a Jira key, meeting notes) is the
starting point. If there is none, ask for the requirement in one line and start.

## Phase 1: grill

Call the Skill tool with "grilling" and follow it: rounds, a numbered frontier,
a recommended answer for each question, "yes" accepts it. Speak the user's
language (Factory notes → Language in AGENTS.md) and keep code names in English.

Before the first round, read `AGENTS.md` (hub: system map, cross-repo rules,
Factory notes), `factory/repos.json`, and the hub's documents in `docs/`: the BRD
items, specs and ADRs the requirement touches. They are the source of truth, so:

- don't ask what they already answer; cite them instead (`per [BR-004]`);
- when the idea contradicts them, make that a question of its own: change the
  document, or change the idea;
- when the idea brings new external material (a link, a page, a file), register
  and snapshot it with the `researcher` agent (Job A) so the issue cites `[S-xxx]`.

Seed the design tree with the branches below plus every item in
**Factory notes → Grill checklist**. Not
every branch applies; close a branch out loud ("no schema change, because …")
rather than skipping it silently.

1. **Problem and users** — who hits this (which users, in which app, or which
   batch job), what they do today, what changes for them.
2. **Repos** — which repo keys change. Name the ones that don't.
3. **Behaviour** — the flow step by step, including empty, loading, error and
   expired-session states; exact copy for anything a user reads.
4. **Interface contract** — endpoints or messages (method, path, auth),
   request and response shapes, error codes; backward compatibility for
   callers already deployed.
5. **Data** — tables and columns, the migration, backfills; any paired change a
   `repos.json` rule requires in another repo.
6. **External systems** — third-party APIs, queues, storage, email/SMS/push;
   whether the local stack (`dev/compose.yaml`) mocks them or new mocks are needed.
7. **Security and sensitive data** — auth, permissions and roles, anything on
   the Factory notes' Sensitive data list, what may be logged.
8. **Config and rollout** — new env vars (and the deploy repo changes they
   need), feature flags, merge and deploy order.
9. **Acceptance** — the observable checks that prove it works, per repo.
10. **Scope and slicing** — what is out, and whether this is one factory job
    or several (see Phase 2).

**Facts are yours.** Whenever a question depends on what the code does today
(an existing endpoint, a DTO, a column, a screen, an RBAC permission, a mock),
dispatch an `Explore` sub-agent on the repo under `repos/` with a narrow
question and keep asking the rest of the frontier while it runs. Cite what it
found (`<key>:src/…`) in your next round. Never ask the user for
something the code can answer. Read `.env.example` files only, never `.env`.

**Decisions are theirs.** Product rules, user-facing copy, which users get what,
deadlines and trade-offs go to the user, each with your recommendation.

Stop grilling when the frontier is empty, then play the design back in a short
summary (decisions, repos, contract, acceptance) and ask:
"Is this our shared understanding?" (in the user's language) Don't write issues before a yes.

## Phase 2: write the issues

**Slice.** One factory job = one issue = one small PR per repo. If the design
is bigger than that, split it into tracer-bullet issues: each one a thin,
working, end-to-end slice (API + UI + tests) that can merge on its own,
blockers first. A slice that only adds an endpoint nobody calls yet is fine
when the next issue is blocked by it. Show the list (title, repos, blocked by,
what it delivers) and let the user adjust it before drafting bodies.

**Draft.** For each issue, fill the template at
`.github/ISSUE_TEMPLATE/factory-requirement.md` exactly: same headings, same
order, every section present (`None.` when empty). Rules:

- Write behaviour, decisions and contracts, not file paths or code. The spec
  writer finds the files. An exact type shape or JSON example is fine in
  Contract.
- `## Decisions` lists every decision settled in the grill, numbered, one line
  each with its reason. Intake treats them as answered and won't ask again.
- `## Acceptance criteria` are checkboxes tagged with the repo, each one
  observable: a request and its response, a screen and what it shows, a test
  that exists.
- `## Open questions` should be `None.` If something is still open, the issue
  isn't ready: say so and go back to grilling, unless the user decides to
  leave it to intake.
- `## Blocked by` lists the issues that must merge first. For a batch not yet
  created, write `Draft 1`, `Draft 2`; you replace them with real numbers when
  creating.

Save each draft to `factory/drafts/<NN>-<slug>.md` (gitignored), show the user
the titles and paths, and print the first draft in full.

**Documents.** If the grill settled something the hub documents should hold, draft
those edits too and show them with the issues:

- a new architecture or technology decision → `factory/bin/docs adr-new "<title>"`,
  filled in with `Status: Proposed`, the options you discussed and the decision;
- a new or changed business rule → the BRD item (`**BR-xxx**`), with its source;
- a changed behaviour → the spec item.

Reference them from the issue (`## Decisions`: `see [ADR-0012]`). Write the
document edits only when the user agrees, at the same time as creating the issues;
ADRs move to `Accepted` when the issue's PRs merge. Run `factory/bin/docs check`
after editing.

**Create.** Only after the user explicitly says to create them (e.g. "สร้างเลย",
"create"), in dependency order (blockers first), from the hub folder:

```bash
gh issue create --title "<title>" --body-file factory/drafts/<NN>-<slug>.md --label factory
```

Ask once which label they want before creating: `factory` puts the issue in the
factory queue now; no label creates it for review first (they add `factory`
later). After each create, replace `Draft <k>` in the remaining drafts with the
real `#<number>`. Report the issue numbers and URLs. Never run `/factory run`
yourself; tell the user it's the next step.

## Never

- Create, edit or label issues without that explicit go-ahead.
- Touch code, branches or PRs in any repo. This skill only reads code and writes
  drafts and issues.
- Put secrets, real customer data (names, citizen ids, phone numbers, policy
  numbers) or `.env` values in an issue. Use made-up examples.

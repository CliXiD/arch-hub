---
name: Factory requirement
about: A requirement for the software factory (written by /grill-issue, or by hand in the same shape)
title: ""
labels: ""
---

<!--
One issue = one factory job = at most one small PR per repo.
Keep every heading, in this order. Write `None.` for an empty section.
Behaviour and decisions, not file paths. No real customer data or secrets.
Add the `factory` label when it's ready to build.
-->

## Problem

Who is affected (which users, in which app, or which batch job), what happens
today, and why it needs to change.

## Behaviour

What the user sees and does when this is done, step by step, including empty,
loading and error states. Exact copy for anything a user reads.

## Repos

<!-- hub:repos -->
- [ ] arch-api — what changes
- [ ] arch-web — what changes
- [ ] arch-deploy — what changes
<!-- /hub:repos -->

## Decisions

Settled during design; intake and the spec writer treat these as answered.

1. <decision> — <reason>

## Contract

Endpoints (method, path, auth), request and response shapes,
error codes; tables and columns; new env vars. `None.` for a single-repo change
with no interface.

## Acceptance criteria

- [ ] [<repo key>] <observable check>

## Out of scope

- <what must not be done in this issue>

## Open questions

None.

## Blocked by

None.

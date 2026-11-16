ESCALATE

## Summary
- Round 2 did what feedback-1 asked: it rebased the job onto main, which now includes CliXiD/arch-api#7 (job 006, `00006_model_vocabulary.sql`). This job's migration was renamed to `00007_source_api.sql`, and the latest-version assertions now expect 7. The behaviour is the same as in round 1.
- arch-api#8 makes three changes:
  - An unknown owner gives 422 at `body.owner` ("team does not exist"), checked before the membership check.
  - Writes made with a service-account token record `source: api`, on the node or edge and in `change_log`.
  - A disallowed kind pair is reported at `body.from` or `body.to`.
- arch-web#6 only regenerates `schema.d.ts`.
- Round 2 has `GATE: PASS` at arch-api `caf60f6` and arch-web `e7307ad`. All four reviews (code, contract, db, security) are `VERDICT: PASS` with no findings, and no Note describes a defect.
- My own spot-checks pass:
  - `TestCheckKindPair` and `TestActorSource` pass.
  - `openapi.yaml` has `api` in all 3 enums.
  - `git diff --stat origin/main -- migrations/` lists only `00007_source_api.sql`.
  - Across repos, the web diff is exactly the 3 widened `source` unions, which match the API enums.

## Why
The work is complete and correct, and the rebase settled the migration-number clash with job 006. It still needs a person: it adds a schema migration that re-creates the CHECK constraint on `change_log`, and it changes what `record()` writes into every `change_log` row. Both are on the Always escalate list ("change_log grants or writes"), and issue Decision 4 asks for human sign-off. The feedback asked for a rebase but gave no sign-off, so that decision is still open.

## Acceptance criteria
1. [arch-api] Unknown owner on POST, as editor and as admin, gives 422 at `body.owner` and writes no `change_log` row: met. The integration subtests `unknown_owner_as_editor` and `unknown_owner_as_admin` sit inside "rejected writes leave no row". In the code, `checkOwner` runs first in the transaction, before `a.can`.
2. [arch-api] PATCH to an unknown owner gives the same 422: met. Covered by the subtest `owner_changed_to_an_unknown_team`. The code runs `can(cur.Owner)`, then `checkOwner`, then `can(new)`.
3. [arch-api] A service token gives `source: api` on the node and in its history entry (`actor_kind: service`); the editor token gives `ui`: met. Covered by `service_account_writes` and the history assertion. `Actor.source()` uses only the server-side `Kind`.
4. [arch-api] `calls` from `eks-prod` gives `body.from`, and `calls` to `eks-prod` gives `body.to`: met. Covered by integration cases, and this still holds with job 006's `external → application` pair. I read `checkKindPair` in the diff.
5. [arch-api] Unit tests for the kind pair and the actor-to-source mapping: met. I re-ran them and they pass.
6. [arch-api] The only new file under `migrations/` holds the three widened checks: met. It is named `00007_source_api.sql`, not `00006`, which the spec's Assumptions allow. I checked it with `git diff --stat` and read the file.
7. [arch-api] No `'ui'` literal is left in `write.sql`, and `openapi-check` passes with `api` in 3 enums: met. Checked in the diff and the gate log; `grep` prints 3.
8. [arch-api] README "Writes" documents the api source, `body.from` and "team does not exist": met, in the diff.
9. [arch-web] `schema.d.ts` has 3 widened unions and is the only changed file: met. I checked with `grep` (3) and `git diff --stat`.

## Merge order
1. CliXiD/arch-api#8. Its migration `00007` runs (Helm migrate job) before the new binary writes `api`.
2. CliXiD/arch-web#6. It works with either API version.

## Docs impact
- [ADR-0016]: the "as built" `change_log` column list says `source ui|yaml|discovery|import`. Add `api` there as a one-line note; no new ADR is needed.

## For the human
The rebase you asked for is done. arch-api#8 now sits on main, which includes #7, and its migration is renamed to `00007_source_api.sql`. Gates and reviews pass again. Two sign-offs are still needed before merging. After that, merge arch-api#8 first and arch-web#6 second.

1. **Migration `migrations/00007_source_api.sql` (CliXiD/arch-api#8).** It drops `nodes_source_check`, `edges_source_check` and `change_log_source_check` and adds them back with `api` included. It only expands them: no grant, trigger or data changes.
   - Re-adding the checks takes a brief ACCESS EXCLUSIVE lock and scans each table. The db review judged this fine at current sizes.
   - `Down` fails once any `api` row exists, because `change_log` is append-only. The file documents this.
2. **The `change_log` write in `internal/model/write.go`.** `record()` now writes `a.source()`: `api` for `actor_kind: service`, otherwise `ui`. This applies to every row a service account writes, including team and environment writes and cascaded edge deletes. Please confirm this is the meaning of `api` you want under [BR-004].

After merging, add `api` to the `change_log` source list in ADR-0016.

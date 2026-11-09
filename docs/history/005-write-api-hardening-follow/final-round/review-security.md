VERDICT: PASS

## Summary
- Edge PATCH/DELETE now read the source node's owner under `FOR SHARE OF n` before `LockEdge`. The permission check can no longer pass on a stale owner while an owner change is still uncommitted ([SPEC-identity-access-05]).
- The lock order (node, then edge) matches `DeleteNode`. Both edge writes call `lockEdgeFor`, and nothing else locks an edge before its node, so I found no new deadlock path.
- The URL password part is now `\S+`. This rejects more values (strictly more URLs are flagged), and RE2 keeps the matching linear, so there's no ReDoS risk.
- `token` is now matched only as a whole word or the end of one. All other name words keep their substring match. This is on the Always escalate list, so a human must sign off the patterns before merge.
- No change to endpoints, guards, the OpenAPI file, migrations or dependencies, no new logging, and no secrets in the diff.

## Findings
None.

## Notes
- The token rule lets more names through than the old substring match did, beyond the examples in the spec. Because only whole words or word ends count, names with `token` at the start of a longer word are now accepted:
  - `tokenvalue`, `tokenid`, `bearertokenvalue` and `authtokens` are accepted.
  - `token_value`, `tokenId` and `xTokenId` are still rejected.

  This follows the spec's rule exactly ("equals or ends with `token`"). The human signing off the patterns should know about it. Value patterns still catch URL passwords, PEM headers and AWS keys whatever the attribute is called.
- `nameWords` splits only on ASCII letters. A name written with non-ASCII look-alike letters (for example a Cyrillic `о` in `tоken`) gets past the check. It got past the old regex too, so this is not new.
- `CreateEdge` still reads the source owner without a lock (`nodeOwnerKind`). The spec leaves this for a later job. The race is narrow: the owner changes while an editor is creating an edge from that node.
- `FOR SHARE OF n` conflicts with the `FOR NO KEY UPDATE` lock taken by an owner `UPDATE`, so it gives the serialisation the spec wants. It doesn't conflict with the FK `FOR KEY SHARE` taken by edge writes. The integration test proves the wait and the 403, with no `change_log` row. The builder also ran it against the old code, where it failed, so the test does catch the race.
- The new `TestSecretsAreNeverEchoed` rows use distinctive values (`https://usr:p@ssw0rd-Qx7@db.example.test`), so the "no 6-character slice is echoed" assertion is meaningful.

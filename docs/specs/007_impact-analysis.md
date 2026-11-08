# Spec 007: impact-analysis

> Status: Draft · Implements: [BR-030], [BR-031], [BR-032], [NFR-005] · Decisions: [ADR-0004], [ADR-0007]
> Repos: arch-api, arch-web · Last reviewed: 2026-11-08

## Summary

For a change request (CR) on a node, this view shows everything along the chain that it could
affect, and who owns it [S-001].

## Behaviour

- **SPEC-impact-analysis-01** The impact of a CR on node X in environment E has two parts. **Upstream (impacted)** is every node that reaches X by following edges forward, transitively: the things that call, depend on, run on, store data in or route via X. **Downstream (dependencies)** is every node X reaches by following edges forward, transitively. `owned_by` edges are never traversed. Cycles are handled, and each node appears once, at its shortest distance. [BR-030]
- **SPEC-impact-analysis-02** `/impact/{env}/{id}` shows X highlighted, with the upstream and downstream subgraphs drawn in different colours, and the rest of the landscape hidden. Each node is labelled with its distance from X. [BR-030]
- **SPEC-impact-analysis-03** Next to the graph, a list groups the impacted nodes by owner team, with counts per team, each node's distance and the edge path that links it to X. The upstream list comes first, because it holds the teams that must be told about the CR. [BR-030]
- **SPEC-impact-analysis-04** The environment can be switched, and the analysis re-runs for the node with the same id in that environment. If there is no such node, the view says so. [BR-030]
- **SPEC-impact-analysis-05** A maximum depth (1–10 or unlimited, default unlimited) and edge-type checkboxes limit the traversal. (Should.) [BR-031]
- **SPEC-impact-analysis-06** The analysis can be given a CR reference (free text or a Jira key), and exported as Markdown or PDF, including the CR reference, the date, the analyst, the filters and the team-grouped lists. A Markdown export is enough for the MVP; PDF comes from the browser's print styles. (Could.) [BR-032]
- **SPEC-impact-analysis-07** An analysis with no upstream nodes says "Nothing depends on <name> in <env>". [BR-030]

## Interfaces

- `GET /api/v1/impact/{environment}/{id}?direction=up|down|both&max_depth=&edge_types=` → `{ "root", "upstream": [{ "node", "distance", "via": [edge_uid...] }], "downstream": [...], "edges": [...], "by_team": { "<team>": { "upstream": n, "downstream": n } } }`.
- Implemented as recursive CTEs over `edges`, with a visited set for cycles ([ADR-0004]).

## Data

- None owned. Saved analyses are not in the MVP.

## Non-functional

- [NFR-005]: an impact query on the 2,000-node / 10,000-edge graph returns in under 2 s with no depth limit; the target is under 500 ms.
- [G-01]: from opening a node to an exported report takes under 1 minute.

## Open questions

- None.

# /hub-init progress

- Phase: **done** (2026-11-08)
- Written: docs/brd.md (2 goals, 15 BR, 8 NFR, Draft); docs/adr/0001-0012 (Accepted);
  docs/specs/001-009 (Draft) + README index; source S-001 (product brief); factory/hub.json
  (mode new, purpose, English); factory/repos.json (3 repos, trunk/rebase, merge order
  api → web → deploy, implies db/infra, auto_merge false); AGENTS.md (system map,
  cross-repo rules, Factory notes).
- Repos created: CliXiD/arch-api, CliXiD/arch-web, CliXiD/arch-deploy (private, README only).
  arch-diagram removed from the hub (still on GitHub).
- Deviations: generated files are not protected_paths (the gate blocks modifying them);
  no repos.json `rules` (they only fire on added files) — OpenAPI → web regen is an AGENTS rule.
- Waiting: branch protection on main (GitHub Pro needed for private repos).
- Open questions: G-02 scope and first teams (brd); cross-env edges (002); routes_via model (006);
  OTLP backend (009) — all khajonpot.
- Next: commit hub; /hub-dev-stack; /grill-issue walking-skeleton per repo; /hub-onboard once code exists.

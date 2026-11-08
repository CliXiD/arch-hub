# Sourced by every factory/checks/<key>.sh. The gate runs a check script from the hub's main
# checkout with the job's worktree as the cwd and FACTORY_HUB, FACTORY_REPO_KEY, FACTORY_BASE set.
# Keep checks fast, deterministic and offline-friendly: no watch modes, no prompts, no services,
# nothing that rewrites tracked files.
set -euo pipefail

step() { echo; echo "== $*"; "$@"; }

# hub_env: put the hub's local env file (dev/env/<key>.env) where repos.json `env.target` says,
# unless the worktree already has one. Never copies a real .env from repos/.
hub_env() {
  local target
  target=$(python3 -c 'import json,sys; r=json.load(open(sys.argv[1]))["repos"][sys.argv[2]]; print((r.get("env") or {}).get("target",""))' \
    "$FACTORY_HUB/factory/repos.json" "$FACTORY_REPO_KEY")
  local src="$FACTORY_HUB/dev/env/$FACTORY_REPO_KEY.env"
  if [ -n "$target" ] && [ ! -f "$target" ] && [ -f "$src" ]; then
    echo "== $target from dev/env/$FACTORY_REPO_KEY.env"
    cp "$src" "$target"
  fi
}

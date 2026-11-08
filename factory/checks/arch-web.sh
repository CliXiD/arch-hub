#!/usr/bin/env bash
# arch-web checks, mirroring CI per [ADR-0010]: ESLint, tsc --noEmit, Vitest (run mode), vite build.
# Playwright e2e needs the local stack and stays out of the gate. Node from .nvmrc ([ADR-0013]), pnpm.
source "$FACTORY_HUB/factory/checks/lib/common.sh"

if [ ! -f package.json ]; then
  echo "== no package.json yet (empty repo): nothing to check"
  exit 0
fi

source "$FACTORY_HUB/factory/checks/lib/node.sh"
node_setup
step pm run lint
step pm run typecheck
step pm run test
hub_env
step pm run build

#!/bin/sh
# arch-web in the dev stack: install with pnpm, run the Vite dev server on :5173. [ADR-0007]
set -eu
if [ ! -f package.json ]; then
  echo "arch-web: no package.json in $(pwd) yet; scaffold the repo first (walking-skeleton issue)." >&2
  exit 1
fi
corepack enable
pnpm install --frozen-lockfile
exec pnpm dev --host 0.0.0.0 --port 5173 --strictPort

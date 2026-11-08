#!/bin/sh
# arch-api in the dev stack: download modules, migrate, serve. [ADR-0003] [SPEC-operations-07]
set -eu
if [ ! -f go.mod ]; then
  echo "arch-api: no go.mod in $(pwd) yet; scaffold the repo first (walking-skeleton issue)." >&2
  exit 1
fi
go mod download
go run ./cmd/arch-api migrate up
exec go run ./cmd/arch-api serve

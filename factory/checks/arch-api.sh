#!/usr/bin/env bash
# arch-api checks, mirroring CI per [ADR-0010]: lint, vet, unit tests, build, OpenAPI staleness.
# Unit tests only: integration tests sit behind `//go:build integration` and stay out of the gate.
# Go comes from go.mod's `toolchain` line ([ADR-0013]); GOTOOLCHAIN=auto downloads it if needed.
# golangci-lint is pinned as a `tool` in go.mod, so it runs with `go tool`.
source "$FACTORY_HUB/factory/checks/lib/common.sh"

if [ ! -f go.mod ]; then
  echo "== no go.mod yet (empty repo): nothing to check"
  exit 0
fi

export GOTOOLCHAIN="${GOTOOLCHAIN:-auto}" GOFLAGS="${GOFLAGS:-} -mod=readonly"
step go version
step go vet ./...
step go tool golangci-lint run ./...
step go test -count=1 ./...
step go build ./...
# Compares a freshly generated spec with the committed api/openapi.yaml without writing tracked files.
step make openapi-check

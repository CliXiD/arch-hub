GATE: PASS
COMMITS: arch-api=8367ce112a246283f4d99f0f1041606fc3bc32c5

## Summary
- arch-api: PASS — checks exit 0 in 12s, commit 8367ce1

## arch-api (repos/arch-api)
Protected paths: none changed.
Checks: exit 0 in 12s. Last 60 lines of checks-arch-api.log:

```

== go version
go version go1.27.2 darwin/arm64

== go vet ./...

== go tool golangci-lint run ./...
0 issues.

== go test -count=1 ./...
ok  	github.com/CliXiD/arch-api/cmd/arch-api	0.415s
?   	github.com/CliXiD/arch-api/cmd/openapi	[no test files]
ok  	github.com/CliXiD/arch-api/internal/auth	1.903s
?   	github.com/CliXiD/arch-api/internal/auth/authtest	[no test files]
ok  	github.com/CliXiD/arch-api/internal/config	0.165s
ok  	github.com/CliXiD/arch-api/internal/db	0.737s
?   	github.com/CliXiD/arch-api/internal/db/dbq	[no test files]
ok  	github.com/CliXiD/arch-api/internal/health	0.505s
ok  	github.com/CliXiD/arch-api/internal/httpapi	6.436s
ok  	github.com/CliXiD/arch-api/internal/model	0.612s
ok  	github.com/CliXiD/arch-api/internal/observability	0.945s
?   	github.com/CliXiD/arch-api/migrations	[no test files]

== go build ./...

== make openapi-check
```

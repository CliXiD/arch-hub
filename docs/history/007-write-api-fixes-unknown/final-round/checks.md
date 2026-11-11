GATE: PASS
COMMITS: arch-api=caf60f6f2f32e1a2e794a562351b8c8ce8de4fc3 arch-web=e7307adbcacaea0de1c0596e3606adc0fab1fcf2

## Summary
- arch-api: PASS — checks exit 0 in 11s, commit caf60f6
- arch-web: PASS — checks exit 0 in 4s, commit e7307ad

## arch-api (repos/arch-api)
Protected paths: none changed.
Checks: exit 0 in 11s. Last 60 lines of checks-arch-api.log:

```

== go version
go version go1.27.2 darwin/arm64

== go vet ./...

== go tool golangci-lint run ./...
0 issues.

== go test -count=1 ./...
ok  	github.com/CliXiD/arch-api/cmd/arch-api	0.686s
?   	github.com/CliXiD/arch-api/cmd/openapi	[no test files]
ok  	github.com/CliXiD/arch-api/internal/auth	0.793s
?   	github.com/CliXiD/arch-api/internal/auth/authtest	[no test files]
ok  	github.com/CliXiD/arch-api/internal/config	0.801s
ok  	github.com/CliXiD/arch-api/internal/db	0.415s
?   	github.com/CliXiD/arch-api/internal/db/dbq	[no test files]
ok  	github.com/CliXiD/arch-api/internal/health	0.277s
ok  	github.com/CliXiD/arch-api/internal/httpapi	6.504s
ok  	github.com/CliXiD/arch-api/internal/model	1.178s
ok  	github.com/CliXiD/arch-api/internal/observability	1.406s
?   	github.com/CliXiD/arch-api/migrations	[no test files]

== go build ./...

== make openapi-check
```

## arch-web (repos/arch-web)
Protected paths: none changed.
Checks: exit 0 in 4s. Last 60 lines of checks-arch-web.log:

```
== node v26.13.0

== pm run lint

> arch-web@0.1.0 lint /Users/khajonpot/Documents/codes/arch-hub/.worktrees/007-write-api-fixes-unknown/arch-web
> eslint .


== pm run typecheck

> arch-web@0.1.0 typecheck /Users/khajonpot/Documents/codes/arch-hub/.worktrees/007-write-api-fixes-unknown/arch-web
> tsc --noEmit


== pm run test

> arch-web@0.1.0 test /Users/khajonpot/Documents/codes/arch-hub/.worktrees/007-write-api-fixes-unknown/arch-web
> vitest run


 RUN  v5.1.0 /Users/khajonpot/Documents/codes/arch-hub/.worktrees/007-write-api-fixes-unknown/arch-web


 Test Files  5 passed (5)
      Tests  30 passed (30)
   Start at  10:57:54
   Duration  829ms (environment 53%, tests 24%, setup 17%, import 4%, transform 1%)


== pm run build

> arch-web@0.1.0 build /Users/khajonpot/Documents/codes/arch-hub/.worktrees/007-write-api-fixes-unknown/arch-web
> vite build

[36mvite v8.3.6 [32mbuilding client environment for production...[36m[39m
transforming...
✓ 81 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.40 kB │ gzip:   0.27 kB
dist/assets/index-EFWbWZ00.css    8.97 kB │ gzip:   2.57 kB
dist/assets/index-CgRSX6TQ.js   426.58 kB │ gzip: 129.65 kB

[32m✓ built in 71ms[39m
v26.13.0 is already installed.
```

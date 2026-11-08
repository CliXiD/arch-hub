GATE: PASS
COMMITS: arch-api=f2622ac98957f8247b350970ea994a4d7c3bfd16 arch-web=0031c52e6ad5e390f33600e7eed261983ad3642e

## Summary
- arch-api: PASS — checks exit 0 in 7s, commit f2622ac
- arch-web: PASS — checks exit 0 in 4s, commit 0031c52

## arch-api (repos/arch-api)
Protected paths: none changed.
Checks: exit 0 in 7s. Last 60 lines of checks-arch-api.log:

```

== go version
go version go1.27.2 darwin/arm64

== go vet ./...

== go tool golangci-lint run ./...
0 issues.

== go test -count=1 ./...
ok  	github.com/CliXiD/arch-api/cmd/arch-api	0.838s
?   	github.com/CliXiD/arch-api/cmd/openapi	[no test files]
ok  	github.com/CliXiD/arch-api/internal/auth	1.032s
?   	github.com/CliXiD/arch-api/internal/auth/authtest	[no test files]
ok  	github.com/CliXiD/arch-api/internal/config	0.157s
ok  	github.com/CliXiD/arch-api/internal/db	1.088s
?   	github.com/CliXiD/arch-api/internal/db/dbq	[no test files]
ok  	github.com/CliXiD/arch-api/internal/health	1.419s
ok  	github.com/CliXiD/arch-api/internal/httpapi	2.423s
ok  	github.com/CliXiD/arch-api/internal/model	0.949s
ok  	github.com/CliXiD/arch-api/internal/observability	1.311s
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

> arch-web@0.1.0 lint /Users/khajonpot/Documents/codes/arch-hub/.worktrees/003-harden-auth-and-http/arch-web
> eslint .


== pm run typecheck

> arch-web@0.1.0 typecheck /Users/khajonpot/Documents/codes/arch-hub/.worktrees/003-harden-auth-and-http/arch-web
> tsc --noEmit


== pm run test

> arch-web@0.1.0 test /Users/khajonpot/Documents/codes/arch-hub/.worktrees/003-harden-auth-and-http/arch-web
> vitest run


 RUN  v5.1.0 /Users/khajonpot/Documents/codes/arch-hub/.worktrees/003-harden-auth-and-http/arch-web


 Test Files  5 passed (5)
      Tests  30 passed (30)
   Start at  05:34:13
   Duration  833ms (environment 57%, tests 22%, setup 16%, import 3%, transform 1%)


== pm run build

> arch-web@0.1.0 build /Users/khajonpot/Documents/codes/arch-hub/.worktrees/003-harden-auth-and-http/arch-web
> vite build

[36mvite v8.3.6 [32mbuilding client environment for production...[36m[39m
transforming...
✓ 81 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.40 kB │ gzip:   0.27 kB
dist/assets/index-EFWbWZ00.css    8.97 kB │ gzip:   2.57 kB
dist/assets/index-CgRSX6TQ.js   426.58 kB │ gzip: 129.65 kB

[32m✓ built in 72ms[39m
v26.13.0 is already installed.
```

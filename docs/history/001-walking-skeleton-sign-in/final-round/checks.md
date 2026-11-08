GATE: PASS
COMMITS: arch-api=7da7dce7daac40720e8adc0503b38ca8543a8238 arch-web=8c678f573b8cfe250904a4fd73f2850e0e395b85

## Summary
- arch-api: PASS — checks exit 0 in 6s, commit 7da7dce
- arch-web: PASS — checks exit 0 in 4s, commit 8c678f5

## arch-api (repos/arch-api)
Protected paths: none changed.
Checks: exit 0 in 6s. Last 60 lines of checks-arch-api.log:

```

== go version
go version go1.27.2 darwin/arm64

== go vet ./...

== go tool golangci-lint run ./...
0 issues.

== go test -count=1 ./...
ok  	github.com/CliXiD/arch-api/cmd/arch-api	0.303s
?   	github.com/CliXiD/arch-api/cmd/openapi	[no test files]
ok  	github.com/CliXiD/arch-api/internal/auth	0.782s
?   	github.com/CliXiD/arch-api/internal/auth/authtest	[no test files]
ok  	github.com/CliXiD/arch-api/internal/config	0.409s
ok  	github.com/CliXiD/arch-api/internal/db	0.667s
ok  	github.com/CliXiD/arch-api/internal/health	0.986s
ok  	github.com/CliXiD/arch-api/internal/httpapi	1.769s
ok  	github.com/CliXiD/arch-api/internal/observability	0.881s
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

> arch-web@0.1.0 lint /Users/khajonpot/Documents/codes/arch-hub/.worktrees/001-walking-skeleton-sign-in/arch-web
> eslint .


== pm run typecheck

> arch-web@0.1.0 typecheck /Users/khajonpot/Documents/codes/arch-hub/.worktrees/001-walking-skeleton-sign-in/arch-web
> tsc --noEmit


== pm run test

> arch-web@0.1.0 test /Users/khajonpot/Documents/codes/arch-hub/.worktrees/001-walking-skeleton-sign-in/arch-web
> vitest run


 RUN  v5.1.0 /Users/khajonpot/Documents/codes/arch-hub/.worktrees/001-walking-skeleton-sign-in/arch-web


 Test Files  5 passed (5)
      Tests  24 passed (24)
   Start at  23:37:52
   Duration  702ms (environment 58%, tests 19%, setup 17%, import 4%, transform 1%, worker 1%)


== pm run build

> arch-web@0.1.0 build /Users/khajonpot/Documents/codes/arch-hub/.worktrees/001-walking-skeleton-sign-in/arch-web
> vite build

[36mvite v8.3.6 [32mbuilding client environment for production...[36m[39m
transforming...
✓ 81 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.40 kB │ gzip:   0.27 kB
dist/assets/index-EFWbWZ00.css    8.97 kB │ gzip:   2.57 kB
dist/assets/index-Dq1-85YE.js   425.31 kB │ gzip: 129.27 kB

[32m✓ built in 72ms[39m
v26.13.0 is already installed.
```

GATE: PASS
COMMITS: arch-api=7dd2588e3dcaa4c18af7e15a82cb7331904e0811 arch-web=bf923f17e283c684896cdb76b23334dd981f0ea9

## Summary
- arch-api: PASS — checks exit 0 in 8s, commit 7dd2588
- arch-web: PASS — checks exit 0 in 4s, commit bf923f1

## arch-api (repos/arch-api)
Protected paths: none changed.
Checks: exit 0 in 8s. Last 60 lines of checks-arch-api.log:

```

== go version
go version go1.27.2 darwin/arm64

== go vet ./...

== go tool golangci-lint run ./...
0 issues.

== go test -count=1 ./...
ok  	github.com/CliXiD/arch-api/cmd/arch-api	1.015s
?   	github.com/CliXiD/arch-api/cmd/openapi	[no test files]
ok  	github.com/CliXiD/arch-api/internal/auth	1.063s
?   	github.com/CliXiD/arch-api/internal/auth/authtest	[no test files]
ok  	github.com/CliXiD/arch-api/internal/config	1.402s
ok  	github.com/CliXiD/arch-api/internal/db	0.465s
?   	github.com/CliXiD/arch-api/internal/db/dbq	[no test files]
ok  	github.com/CliXiD/arch-api/internal/health	0.193s
ok  	github.com/CliXiD/arch-api/internal/httpapi	3.416s
ok  	github.com/CliXiD/arch-api/internal/model	1.192s
ok  	github.com/CliXiD/arch-api/internal/observability	1.612s
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

> arch-web@0.1.0 lint /Users/khajonpot/Documents/codes/arch-hub/.worktrees/002-model-tables-seeds-and/arch-web
> eslint .


== pm run typecheck

> arch-web@0.1.0 typecheck /Users/khajonpot/Documents/codes/arch-hub/.worktrees/002-model-tables-seeds-and/arch-web
> tsc --noEmit


== pm run test

> arch-web@0.1.0 test /Users/khajonpot/Documents/codes/arch-hub/.worktrees/002-model-tables-seeds-and/arch-web
> vitest run


 RUN  v5.1.0 /Users/khajonpot/Documents/codes/arch-hub/.worktrees/002-model-tables-seeds-and/arch-web


 Test Files  5 passed (5)
      Tests  24 passed (24)
   Start at  00:33:57
   Duration  807ms (environment 62%, setup 17%, tests 16%, import 3%, transform 1%)


== pm run build

> arch-web@0.1.0 build /Users/khajonpot/Documents/codes/arch-hub/.worktrees/002-model-tables-seeds-and/arch-web
> vite build

[36mvite v8.3.6 [32mbuilding client environment for production...[36m[39m
transforming...
✓ 81 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.40 kB │ gzip:   0.27 kB
dist/assets/index-EFWbWZ00.css    8.97 kB │ gzip:   2.57 kB
dist/assets/index-Dq1-85YE.js   425.31 kB │ gzip: 129.27 kB

[32m✓ built in 86ms[39m
v26.13.0 is already installed.
```

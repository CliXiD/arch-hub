One file per repo key: `<key>.env`, local-only dummy values that point at `dev/compose.yaml`.
`dev/bin/apply-env` copies each to the repo at `env.target` in `factory/repos.json`; the
factory's checks copy it into worktrees. Never put real credentials or copies of real `.env`
files here.

# Node helpers. Source common.sh first.
#
# use_node: switch to the version in .nvmrc / .node-version with fnm or nvm (installing it if
#           needed); fail clearly when neither is available and the current Node differs.
# node_setup: use_node, then install from the lockfile on a fresh worktree and again only when
#           the lockfile or Node version changes. Detects npm, pnpm or yarn from the lockfile.
# pm: the detected package manager command, e.g. `pm run lint`.

use_node() {
  local want have f
  for f in .nvmrc .node-version; do
    [ -f "$f" ] && { want=$(tr -d ' v\r\n' < "$f"); break; }
  done
  [ -z "${want:-}" ] && { echo "== node $(node -v)"; return 0; }
  case "$want" in lts/*|node|stable) echo "== node $(node -v) (.nvmrc says $want)"; return 0 ;; esac
  have=$(node -v 2>/dev/null | tr -d v || true)
  if [ "$have" != "$want" ] && [ "${have%%.*}" != "$want" ]; then
    if command -v fnm >/dev/null 2>&1; then
      eval "$(fnm env --shell bash)"
      fnm use --install-if-missing "$want" >/dev/null
    elif [ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]; then
      set +u; . "${NVM_DIR:-$HOME/.nvm}/nvm.sh"; nvm install "$want" >/dev/null && nvm use "$want" >/dev/null; set -u
    fi
    have=$(node -v 2>/dev/null | tr -d v || true)
  fi
  if [ "$have" != "$want" ] && [ "${have%%.*}" != "$want" ]; then
    echo "checks: this repo needs Node $want but found ${have:-none}. Install it once: brew install fnm && fnm install $want" >&2
    exit 1
  fi
  echo "== node v$have"
}

PM=npm
if [ -f pnpm-lock.yaml ]; then PM=pnpm; elif [ -f yarn.lock ]; then PM=yarn; elif [ -f bun.lockb ] || [ -f bun.lock ]; then PM=bun; fi
pm() { "$PM" "$@"; }

node_setup() {
  use_node
  local lock stamp=node_modules/.factory-lock-hash hash
  for lock in package-lock.json pnpm-lock.yaml yarn.lock bun.lock bun.lockb; do [ -f "$lock" ] && break; done
  hash="$(node -v)-$( (shasum "$lock" 2>/dev/null || sha1sum "$lock") | cut -d' ' -f1)"
  if [ ! -d node_modules ] || [ "$(cat "$stamp" 2>/dev/null)" != "$hash" ]; then
    echo "== install ($PM)"
    case "$PM" in
      npm) npm ci --prefer-offline --no-audit --no-fund ;;
      pnpm) corepack enable >/dev/null 2>&1 || true; pnpm install --frozen-lockfile ;;
      yarn) corepack enable >/dev/null 2>&1 || true; yarn install --frozen-lockfile 2>/dev/null || yarn install --immutable ;;
      bun) bun install --frozen-lockfile ;;
    esac
    echo "$hash" > "$stamp"
  fi
}

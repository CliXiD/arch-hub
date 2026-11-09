#!/usr/bin/env bash
# Print an access token from the LOCAL dev Keycloak (hub dev/keycloak/arch-realm.json, dummy
# credentials only). Never use it against a real realm.
#
#   docs/architecture/dev-token.sh ci            # client credentials, arch-ci-platform (editor, team platform)
#   docs/architecture/dev-token.sh user admin    # Auth Code + PKCE as a seeded user (password "password")
#
# The `user` mode drives the realm's login form with curl on behalf of the public arch-web
# client, since no client in the dev realm allows the password grant.
set -euo pipefail
KC=${KC:-http://localhost:8180/realms/arch}
case ${1:-} in
  ci)
    curl -sS "$KC/protocol/openid-connect/token" -d grant_type=client_credentials \
      -d client_id=arch-ci-platform -d client_secret=dev-ci-secret | jq -er .access_token ;;
  user)
    u=${2:?user name, e.g. admin}
    jar=$(mktemp); trap 'rm -f "$jar"' EXIT
    ver=$(head -c 48 /dev/urandom | base64 | tr -d '=+/\n' | cut -c1-64)
    chal=$(printf %s "$ver" | openssl dgst -binary -sha256 | base64 | tr '+/' '-_' | tr -d '=\n')
    redir=http://localhost:5173/callback
    page=$(curl -sS -c "$jar" -b "$jar" -G "$KC/protocol/openid-connect/auth" \
      --data-urlencode client_id=arch-web --data-urlencode response_type=code \
      --data-urlencode scope=openid --data-urlencode redirect_uri=$redir \
      --data-urlencode code_challenge="$chal" --data-urlencode code_challenge_method=S256)
    action=$(printf %s "$page" | grep -o 'action="[^"]*"' | head -1 | sed 's/^action="//;s/"$//;s/&amp;/\&/g')
    loc=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{redirect_url}' "$action" \
      --data-urlencode username="$u" --data-urlencode password=password)
    code=$(printf %s "$loc" | sed -n 's/.*[?&]code=\([^&]*\).*/\1/p')
    [ -n "$code" ] || { echo "dev-token: login failed for $u" >&2; exit 1; }
    curl -sS "$KC/protocol/openid-connect/token" -d grant_type=authorization_code -d client_id=arch-web \
      -d code="$code" -d redirect_uri=$redir -d code_verifier="$ver" | jq -er .access_token ;;
  *) sed -n '2,10p' "$0" >&2; exit 2 ;;
esac

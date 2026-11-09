#!/usr/bin/env bash
# Model Architecture E2E's own production architecture in Architecture E2E, through its write API.
#
#   ARCH_API_URL=http://localhost:5300 ARCH_TOKEN=<editor token, team platform> \
#     [ARCH_ADMIN_TOKEN=<admin token>] docs/architecture/self-model.sh
#
# Re-runnable: nodes and edges that already exist are updated in place (If-Match) to match this
# file. The owner team `platform` is created with ARCH_ADMIN_TOKEN when it is missing (creating a
# team needs the admin role). Facts come from docs/adr (0003, 0004, 0006, 0008, 0009, 0011, 0012,
# 0014) and docs/specs/009_operations.md; names are examples, never real hostnames or IPs.
# Needs bash, curl and jq. Tokens are never printed.
set -euo pipefail

: "${ARCH_API_URL:?set ARCH_API_URL, e.g. http://localhost:5300}"
: "${ARCH_TOKEN:?set ARCH_TOKEN (an editor token with team platform)}"
ENV=${ARCH_ENVIRONMENT:-prod}
TEAM=platform
API="${ARCH_API_URL%/}/api/v1"
BODY=$(mktemp); trap 'rm -f "$BODY"' EXIT

# call <token> <method> <path> [json] [if-match] -> sets STATUS, response body in $BODY
call() {
  local tok=$1 method=$2 path=$3 data=${4:-} match=${5:-}
  local args=(-sS -o "$BODY" -w '%{http_code}' -X "$method" -H "Authorization: Bearer $tok"
    -H 'Accept: application/json')
  [ -n "$data" ] && args+=(-H 'Content-Type: application/json' --data "$data")
  [ -n "$match" ] && args+=(-H "If-Match: $match")
  STATUS=$(curl "${args[@]}" "$API$path")
}
fail() { echo "self-model: $1 -> HTTP $STATUS" >&2; jq . "$BODY" >&2 2>/dev/null || cat "$BODY" >&2; exit 1; }

ensure_team() {
  call "$ARCH_TOKEN" GET /teams
  [ "$STATUS" = 200 ] || fail "GET /teams"
  if jq -e --arg t "$TEAM" '.items[] | select(.id == $t)' "$BODY" >/dev/null; then return; fi
  : "${ARCH_ADMIN_TOKEN:?team $TEAM is missing; set ARCH_ADMIN_TOKEN (admin role) to create it}"
  call "$ARCH_ADMIN_TOKEN" POST /teams "$(jq -nc --arg t "$TEAM" '{id: $t, name: "Platform"}')"
  [ "$STATUS" = 201 ] || fail "POST /teams $TEAM"
  echo "team   $TEAM created"
}

# node <id> <type> <name> <description> <tags json> <attributes json>
node() {
  local id=$1 type=$2 name=$3 desc=$4 tags=$5 attrs=$6
  local patch; patch=$(jq -nc --arg n "$name" --arg d "$desc" --argjson t "$tags" --argjson a "$attrs" \
    '{name: $n, description: $d, owner: "'$TEAM'", tags: $t, attributes: $a}')
  call "$ARCH_TOKEN" POST /nodes "$(jq -c --arg e "$ENV" --arg i "$id" --arg ty "$type" \
    '. + {environment: $e, id: $i, type: $ty}' <<<"$patch")"
  case $STATUS in
    201) echo "node   $id created" ;;
    409) call "$ARCH_TOKEN" GET "/nodes/$ENV/$id"; [ "$STATUS" = 200 ] || fail "GET node $id"
         local v; v=$(jq -r .version "$BODY")
         call "$ARCH_TOKEN" PATCH "/nodes/$ENV/$id" "$patch" "\"$v\""
         [ "$STATUS" = 200 ] || fail "PATCH node $id"; echo "node   $id updated" ;;
    *)   fail "POST node $id" ;;
  esac
}

# edge <type> <from> <to> <attributes json>
edge() {
  local type=$1 from=$2 to=$3 attrs=$4
  call "$ARCH_TOKEN" POST /edges "$(jq -nc --arg e "$ENV" --arg ty "$type" --arg f "$from" --arg t "$to" \
    --argjson a "$attrs" '{environment: $e, type: $ty, from: $f, to: $t, attributes: $a}')"
  case $STATUS in
    201) echo "edge   $from -[$type]-> $to created" ;;
    409) call "$ARCH_TOKEN" GET "/edges?environment=$ENV&type=$type&from=$from&to=$to"
         [ "$STATUS" = 200 ] || fail "GET edge $from $type $to"
         local uid v; uid=$(jq -r '.items[0].uid' "$BODY"); v=$(jq -r '.items[0].version' "$BODY")
         call "$ARCH_TOKEN" PATCH "/edges/$uid" "$(jq -nc --argjson a "$attrs" '{attributes: $a}')" "\"$v\""
         [ "$STATUS" = 200 ] || fail "PATCH edge $from $type $to"; echo "edge   $from -[$type]-> $to updated" ;;
    *)   fail "POST edge $from $type $to" ;;
  esac
}

ensure_team

# --- Nodes -----------------------------------------------------------------------------------
# Clients. The model has no "client" or "actor" type and external nodes cannot be the source of a
# `calls` edge, so browsers and CI are application/service nodes tagged `client` (see README).
node users-browser service "Users' browsers" \
  "Engineers and architects using the SPA; sign in with OIDC Auth Code + PKCE [ADR-0008]." \
  '["client","users"]' '{"runtime":"web browser"}'
node team-ci service "Team CI pipelines" \
  "Each team's CI pushes its architecture YAML with the arch CLI [ADR-0006]." \
  '["client","ci"]' '{"identity":"confidential client, client credentials"}'
node arch-cli service "arch CLI" \
  "Go CLI built from arch-api/cmd/arch; validates and pushes YAML [ADR-0006]." \
  '["client","cli"]' '{"language":"go","source":"arch-api/cmd/arch"}'

# Apps (images from GHCR, installed by the arch-deploy Helm chart on EKS) [ADR-0009].
node arch-web service "arch-web" \
  "React SPA served by nginx; reads runtime config from /config.json [ADR-0007] [SPEC-operations-06]." \
  '["app","helm:arch"]' '{"framework":"react","server":"nginx","image":"ghcr.io/example-org/arch-web"}'
node arch-api service "arch-api" \
  "Go REST API (gin + Huma v2): typed graph, impact queries, YAML import/export, arch CLI backend, audit log [ADR-0003]." \
  '["app","helm:arch"]' '{"language":"go","framework":"gin + huma v2","api":"/api/v1","metrics_port":9090,"image":"ghcr.io/example-org/arch-api"}'
node arch-migrate service "arch-api migrate job" \
  "Helm pre-upgrade hook running arch-api migrate up (goose) as the schema owner [ADR-0004] [ADR-0014]." \
  '["app","job","helm:arch"]' '{"command":"arch-api migrate up","image":"ghcr.io/example-org/arch-api"}'

# Platform: identity, data, observability, secrets.
node keycloak saas "Keycloak realm arch" \
  "The organisation's Keycloak; realm arch with roles viewer/editor/admin and a teams claim [ADR-0008]." \
  '["identity","platform"]' '{"realm":"arch","roles":["viewer","editor","admin"]}'
node arch-db database "PostgreSQL 16 (RDS)" \
  "Amazon RDS for PostgreSQL 16; owner role arch for migrations, runtime role arch_app [ADR-0004] [ADR-0014]." \
  '["data","platform"]' '{"engine":"postgres","version":"16","service":"rds","port":5432}'
node otel-collector service "OTLP trace collector" \
  "Receives OpenTelemetry traces from arch-api; Jaeger in the local stack [ADR-0011]." \
  '["observability","platform"]' '{"protocol":"otlp","local":"jaeger"}'
node secrets-manager saas "AWS Secrets Manager" \
  "Source of the api's secrets through External Secrets [ADR-0012] [SPEC-operations-07]." \
  '["secrets","platform"]' '{"sync":"external secrets operator"}'

# Build & deploy.
node ghcr saas "GHCR" \
  "GitHub Container Registry; each app repo pushes its image tagged with the git SHA [ADR-0009]." \
  '["build","registry"]' '{"registry":"ghcr.io/example-org"}'
node eks k8s-cluster "EKS cluster" \
  "AWS EKS; arch-deploy's Helm chart installs api, web and the migrate job [ADR-0009]." \
  '["build","deploy","cluster"]' '{"provider":"aws","chart":"arch-deploy","envs":["dev","prod"]}'

# Network.
node app-vpc vpc "Application VPC" \
  "The AWS VPC holding the EKS cluster and RDS; the ingress is the only way in [SPEC-operations-02]." \
  '["network"]' '{"provider":"aws","entry":"kubernetes ingress (load balancer)"}'

# --- Edges -----------------------------------------------------------------------------------
edge calls users-browser arch-web '{"protocol":"https","port":443,"path":"/","via":"ingress","purpose":"SPA assets"}'
edge calls users-browser arch-api '{"protocol":"https","port":443,"path":"/api/v1","via":"ingress","auth":"bearer jwt","purpose":"REST API"}'
edge calls users-browser keycloak '{"protocol":"https","port":443,"flow":"oidc auth code + pkce","purpose":"sign-in"}'
edge routes_via users-browser app-vpc '{"protocol":"https","port":443,"entry":"ingress"}'

edge depends_on team-ci arch-cli '{"purpose":"arch push in CI"}'
edge calls arch-cli keycloak '{"protocol":"https","port":443,"flow":"oidc client credentials","purpose":"service token"}'
edge calls arch-cli arch-api '{"protocol":"https","port":443,"path":"/api/v1/import","payload":"yaml","purpose":"import"}'
edge routes_via arch-cli app-vpc '{"protocol":"https","port":443,"entry":"ingress"}'

edge depends_on arch-web arch-api '{"contract":"api/openapi.yaml","purpose":"generated client"}'
edge calls arch-api keycloak '{"protocol":"https","port":443,"path":"/realms/arch/protocol/openid-connect/certs","purpose":"jwks"}'
edge calls arch-api otel-collector '{"protocol":"grpc","port":4317,"purpose":"otlp traces"}'
edge stores_data_in arch-api arch-db '{"protocol":"pgx","port":5432,"role":"arch_app"}'
edge stores_data_in arch-migrate arch-db '{"protocol":"pgx","port":5432,"role":"arch","purpose":"goose migrations"}'
edge depends_on arch-api secrets-manager '{"purpose":"secrets via external secrets"}'

edge runs_on arch-web eks '{"workload":"deployment"}'
edge runs_on arch-api eks '{"workload":"deployment"}'
edge runs_on arch-migrate eks '{"workload":"helm pre-upgrade job"}'
edge depends_on arch-web ghcr '{"purpose":"image pull","image":"arch-web"}'
edge depends_on arch-api ghcr '{"purpose":"image pull","image":"arch-api"}'
edge depends_on arch-migrate ghcr '{"purpose":"image pull","image":"arch-api"}'

edge routes_via eks app-vpc '{"role":"cluster network"}'
edge routes_via arch-db app-vpc '{"role":"private subnets","port":5432}'

echo "done: environment $ENV"

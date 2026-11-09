# Architecture picture (dogfood)

![Architecture E2E: clients, network, applications, platform and build & deploy](architecture.svg)

`architecture.svg` shows how Architecture E2E itself is built and deployed in `prod`: users'
browsers and team CI (with the arch CLI) reach `arch-web` and `arch-api` through the VPC ingress
and sign in with Keycloak; `arch-api` stores data in PostgreSQL 16 on RDS, checks tokens against
the realm's JWKS, sends OTLP traces to a collector and reads its secrets from AWS Secrets Manager;
the Helm release from `arch-deploy` runs the api, the web app and the migrate job on EKS from GHCR
images. Facts come from [ADR-0003], [ADR-0004], [ADR-0006], [ADR-0008], [ADR-0009], [ADR-0011],
[ADR-0012], [ADR-0014] and [SPEC-operations-07]; names such as `example-org` are examples.

## How it was made

The product modelled itself. `self-model.sh` creates every node and edge through the product's own
write API (`POST /api/v1/nodes`, `POST /api/v1/edges`, owner team `platform`), `GET /api/v1/graph`
exported the model to `self-model.graph.json`, and `render.py` (Python standard library only)
draws the SVG from that JSON. The layout is driven by the data (lane by kind, type and tags;
order by neighbours; `helm:<release>` tags draw the release box), not placed by node name.

| file | what it is |
|---|---|
| `self-model.sh` | the model as code: 13 nodes, 22 edges in `prod`; re-runnable (updates in place with `If-Match`) |
| `self-model.graph.json` | `GET /api/v1/graph?environment=prod`, pretty-printed |
| `render.py` | `self-model.graph.json` → `architecture.svg` (light and dark themes) |
| `dev-token.sh` | tokens from the local dev Keycloak only (dummy credentials) |

## Regenerate

From the hub, with the dev stack up (`dev/bin/stack up`). The model lives in its own database
`arch_dogfood`, so the `arch` dev database is untouched:

```bash
# once: database and schema
podman exec architecture-e2e-dev-postgres-1 psql -U arch -d postgres \
  -c "CREATE DATABASE arch_dogfood OWNER arch" -c "GRANT CONNECT ON DATABASE arch_dogfood TO arch_app"
cd repos/arch-api && set -a && . ../../dev/env/arch-api.env && set +a
export DATABASE_URL=postgres://arch_app:arch_app@localhost:5432/arch_dogfood?sslmode=disable
export MIGRATE_DATABASE_URL=postgres://arch:arch@localhost:5432/arch_dogfood?sslmode=disable
export HTTP_ADDR=:5300 METRICS_ADDR=:5301
go run ./cmd/arch-api migrate up
go run ./cmd/arch-api serve &          # stop it with: kill %1
cd ../..

# load the model (ARCH_ADMIN_TOKEN is only needed while team `platform` does not exist yet)
ARCH_API_URL=http://localhost:5300 ARCH_TOKEN=$(docs/architecture/dev-token.sh ci) \
  ARCH_ADMIN_TOKEN=$(docs/architecture/dev-token.sh user admin) docs/architecture/self-model.sh

# export and draw
curl -s -H "Authorization: Bearer $(docs/architecture/dev-token.sh ci)" \
  "http://localhost:5300/api/v1/graph?environment=prod" | jq . > docs/architecture/self-model.graph.json
python3 docs/architecture/render.py
```

## Dogfood findings

What we hit while modelling the product in itself (arch-api `main` at `e6c3caa`):

1. **No client or actor type, and external nodes can't start an edge.** Users' browsers and team
   CI have no fitting type; as `external` nodes they could not call anything:
   `422 /problems/validation` "edge type calls does not allow external → application". They are
   `application`/`service` nodes tagged `client`, so they show up as applications (7 instead of 4)
   in lists and impact results.
2. **Missing types, and no way to add one.** No type for an ingress/load balancer, a container
   registry, a Helm release or a Kubernetes job. The type write endpoints ([SPEC-admin-01]) are
   still pending, so the ingress is an edge attribute (`via: ingress`), GHCR and Secrets Manager are
   `saas`, the Helm release is a `helm:arch` tag, and the migrate job is a `service`.
3. **A fresh database needs an admin before CI can write anything.** No team exists after
   migrations, creating one needs the admin role (`403 /problems/forbidden` "requires role
   admin" for the CI client), and the dev realm has no non-interactive admin login (no password
   grant), so `dev-token.sh user admin` drives the Keycloak login form with curl.
4. **Unknown owner team reads as a permission error.** `owner: "no-such-team"` returns
   `403 /problems/forbidden` "node is owned by team no-such-team", not a `422` naming the field.
5. **Edge vocabulary is thin.** `calls.protocol` has no value for Postgres, OIDC or OTLP (`"otlp"`
   → `422` "is not one of the allowed values"), and `stores_data_in`, `depends_on`, `runs_on` and
   `routes_via` declare no attributes. Undeclared attributes are accepted, so port, path, flow and
   role are free-form keys that nothing validates.
6. **API writes are recorded as `source: ui`.** Every change made by the script with a service
   token shows `source: ui` in the history; only `actor_kind: service` tells it apart.
7. **Disallowed kind pair blames `body.to`** even when the source's kind is the problem (item 1).

Worked as specified: `If-Match` on `PATCH /nodes` (no header `428`, stale `412`, current `200`
with `ETag: "2"`), a PATCH with unchanged values keeps the version and writes no history row, a
node's history includes its edges, and `/graph` is gzipped.

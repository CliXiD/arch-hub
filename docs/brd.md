# Business Requirements — Architecture E2E

> Status: Draft · Owner: khajonpot · Last reviewed: 2026-11-08
> Sources: [S-001]; everything else decided in /hub-init on 2026-11-08 with khajonpot.

## 1. Background and problem

An application rarely stands alone. A service running in AWS EKS needs an RDS Postgres
database, and it calls an API on an on-prem application that it can only reach through the
landing zone [S-001]. Nobody holds this end-to-end (E2E) chain in one place: it is spread
across diagrams, wikis and people's heads. So when a change request (CR) hits one
application, its impact on the rest of the chain is estimated by asking around. Estimates
are slow and links get missed.

Architecture E2E is an internal tool that models every application, its infrastructure, the
on-prem and external systems it uses, and the integrations and network paths between them as
one typed graph. Two views answer the main questions: from an application's point of view,
what does it depend on and what is linked to it, and for a CR, what is impacted along the
whole chain [S-001].

## 2. Goals and success measures

- **G-01** Make the impact of a CR visible across the whole chain — measured by producing a CR impact report in under 1 minute (today: hours of asking around). [S-001]
- **G-02** One shared map of the E2E architecture — measured by ≥ 80% of in-scope applications modelled within 3 months of go-live. Source: decided in /hub-init on 2026-11-08.

## 3. Out of scope

- Live monitoring, health or status of the modelled systems (this is a design-time and change-time map, not an observability tool).
- Cost data and cost analysis.
- Auto-remediation or any change made to the real systems.
- Replacing a CMDB.
- Public or anonymous sharing of any part of the model.
- Multi-tenant SaaS: one organisation per installation.

## 4. Stakeholders and users

| Who | Role | Needs |
|---|---|---|
| Engineers | viewer / editor of their team's applications | Model their applications and links; see what they depend on and who depends on them |
| Architects | viewer / editor across teams | The E2E landscape; CR impact analysis; layered views |
| Admins | admin | Manage node and edge types, teams and roles |
| khajonpot | product owner, docs owner, decides business rules | — |

## 5. Business requirements

### Model

- **BR-001** The model is a typed graph. Node types: Application/Service, Infrastructure resource (cluster, database, queue, bucket, ...), Network element (VPC, landing zone, transit gateway, VPN/Direct Connect, firewall, ...), External or on-prem system, and Project/Team. Edge types: `depends_on`, `calls` (with protocol and port), `runs_on`, `stores_data_in`, `routes_via` (network path) and `owned_by` — priority Must. [S-001]
- **BR-002** Every node has an environment (for example dev, uat, prod) and an owner team — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-003** Admins can add node and edge types and their attributes without a code change — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-004** Every node and edge records where it came from (`ui`, `api` for writes by a service account through the API, `yaml`, and later `discovery` or `import`), so later ingestion paths fit in — priority Must. Source: decided in /hub-init on 2026-11-08; `api` added in /grill-issue on 2026-11-09 (hub issue #18).

### Ingestion

- **BR-010** Editors create, edit and delete nodes and edges through forms in the UI — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-011** Architecture as code: a team describes its slice of the model in a YAML file (validated by a published JSON Schema). The YAML is imported through the API or the `arch` CLI (for example from the team's CI) by upserting on stable ids, and any slice can be exported back to YAML. The database is the source of truth — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-012** Auto-discovery from AWS (AWS Config, EKS, RDS) and Kubernetes — priority Should. Source: decided in /hub-init on 2026-11-08.
- **BR-013** Import from a CMDB or other existing tools — priority Could. Source: decided in /hub-init on 2026-11-08.

### Views

- **BR-020** An interactive landscape graph of the whole model, with search and filters by type, team and environment — priority Must. [S-001]
- **BR-021** An application focus view: for one node, what it runs on, where it stores data, what it calls, what calls it, and the network path it uses — priority Must. [S-001]
- **BR-022** Layered views (business, application, infrastructure, network) in the style of C4 — priority Should. Source: decided in /hub-init on 2026-11-08.
- **BR-023** Export a diagram to PNG/SVG and to draw.io and Mermaid — priority Could. Source: decided in /hub-init on 2026-11-08.

### Change impact

- **BR-030** For a CR on a node, show the upstream chain (everything that depends on it, transitively) and the downstream chain (everything it depends on, transitively), as a highlighted subgraph and as a list grouped by owner team, filterable by environment — priority Must. [S-001]
- **BR-031** Limit the impact analysis by depth and by edge type — priority Should. Source: decided in /hub-init on 2026-11-08.
- **BR-032** Link an impact analysis to a CR ticket (for example Jira), and save or export the report (PDF/Markdown) — priority Could. Source: decided in /hub-init on 2026-11-08.

### Access, admin and history

- **BR-040** Everyone signs in with the organisation's SSO (Keycloak). Roles: viewer (all signed-in users: read everything), editor (change the nodes and edges owned by their own teams), admin (types, teams, roles and settings) — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-041** Admins manage teams and node and edge types — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-042** Every change to a node or edge is recorded: who changed it, when, and the values before and after. Users can see a node's history — priority Must. Source: decided in /hub-init on 2026-11-08.
- **BR-043** CI pipelines push YAML with a service account, not with a person's credentials — priority Must. Source: decided in /hub-init on 2026-11-08.

## 6. Non-functional requirements

- **NFR-001** Security: all model data (hostnames, IPs, ports, network paths) is internal-confidential. Nothing is visible without SSO, and there are no public or anonymous links. Source: decided in /hub-init on 2026-11-08.
- **NFR-002** No secrets in the model: the tool never stores credentials, passwords, tokens or connection strings with credentials, and rejects fields that look like them on input. Source: decided in /hub-init on 2026-11-08.
- **NFR-003** Audit: the change history ([BR-042]) is append-only and kept indefinitely. Source: decided in /hub-init on 2026-11-08.
- **NFR-004** Availability: 99% during business hours, best effort outside them. Source: decided in /hub-init on 2026-11-08.
- **NFR-005** Performance: a graph of up to 2,000 nodes and 10,000 edges renders in under 3 seconds; an impact query returns in under 2 seconds. Source: decided in /hub-init on 2026-11-08.
- **NFR-006** Accessibility: WCAG 2.1 AA for the UI shell (navigation, forms, lists; the graph canvas has a list alternative). Source: decided in /hub-init on 2026-11-08.
- **NFR-007** Language: English only, for the UI and the documents. Source: decided in /hub-init on 2026-11-08.
- **NFR-008** Observability: structured JSON logs, health and readiness endpoints, Prometheus metrics, and OpenTelemetry traces exported over OTLP. Source: decided in /hub-init on 2026-11-08.

## 7. Constraints and assumptions

- No hard deadline; a small team (the product owner plus the software factory).
- Self-hosted inside the organisation (target: AWS EKS with RDS Postgres); one organisation per installation.
- Identity provider: Keycloak over OIDC.
- Assumption: a graph of the size in [NFR-005] is enough for the first years.

## 8. Open questions

- Which applications and teams count as "in scope" for [G-02], and who onboards the first ones? — khajonpot, before go-live.
- ~~Stable node ids~~ — settled 2026-11-08: author-supplied slug, unique per environment ([SPEC-model-05]).
- ~~Who edits cross-team edges~~ — settled 2026-11-08: the owner of the source node ([SPEC-identity-access-05]).

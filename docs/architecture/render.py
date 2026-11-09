#!/usr/bin/env python3
"""Render docs/architecture/architecture.svg from self-model.graph.json (GET /api/v1/graph).

    python3 docs/architecture/render.py [graph.json] [out.svg]

Python 3 standard library only. The layout comes from the data: every node goes to a lane by its
kind, type and tags (LANES below), nodes are ordered inside a lane by their neighbours, network
nodes become a band that client traffic crosses, and nodes tagged `helm:<release>` are boxed as
one Helm release. Nothing is placed by node name.
"""

import json
import sys
from html import escape
from itertools import permutations
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "self-model.graph.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "architecture.svg"

W, H = 1200, 860
SIDE_STEP = 150                     # vertical distance between build & deploy nodes
NODE_W, NODE_H = 196, 58
MAIN_X0, MAIN_X1 = 40, 900          # clients, network, apps and platform lanes
SIDE_X0, SIDE_X1 = 960, 1160        # build & deploy lane

# lane id -> (title, y of the node row); "side" lanes stack their nodes vertically.
LANES = {
    "clients": ("Clients & CI", 150),
    "network": ("Network", 284),
    "apps": ("Applications", 430),
    "platform": ("Platform, data & observability", 680),
    "build": ("Build & deploy", None),
}
BUILD_TAGS = {"build", "registry", "deploy", "cluster"}


def lane_of(node):
    tags = set(node["tags"])
    if "client" in tags:
        return "clients"
    if node["kind"] == "network":
        return "network"
    if tags & BUILD_TAGS:
        return "build"
    if node["kind"] == "application" and not tags & {"platform", "observability"}:
        return "apps"
    return "platform"


KIND_CLASS = {"application": "k-app", "infrastructure": "k-infra", "network": "k-net",
              "external": "k-ext", "team": "k-team"}
EDGE_CLASS = {"calls": "e-calls", "stores_data_in": "e-data", "depends_on": "e-dep",
              "runs_on": "e-run", "routes_via": "e-route", "owned_by": "e-own"}

STYLE = """
:root{--bg:#ffffff;--fg:#1f2328;--muted:#59636e;--lane:#f6f8fa;--laneline:#d1d9e0;
--app:#ddf4ff;--app-s:#0969da;--infra:#dafbe1;--infra-s:#1a7f37;--net:#fbefff;--net-s:#8250df;
--ext:#fff1e5;--ext-s:#bc4c00;--team:#eaeef2;--team-s:#59636e;
--calls:#0969da;--data:#1a7f37;--dep:#6e7781;--run:#8250df;--route:#8250df;--own:#6e7781;
--chip:#ffffff}
@media (prefers-color-scheme: dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--lane:#151b23;
--laneline:#3d444d;--app:#0c2d6b;--app-s:#4493f8;--infra:#0f3d1f;--infra-s:#3fb950;--net:#2b1a4a;
--net-s:#ab7df8;--ext:#3d1d00;--ext-s:#f0883e;--team:#21262d;--team-s:#9198a1;--calls:#4493f8;
--data:#3fb950;--dep:#9198a1;--run:#ab7df8;--route:#ab7df8;--own:#9198a1;--chip:#0d1117}}
svg{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif}
.bg{fill:var(--bg)} .t{fill:var(--fg)} .m{fill:var(--muted)}
.title{font-size:22px;font-weight:600} .sub{font-size:13px} .lane-t{font-size:11px;font-weight:600;
letter-spacing:.08em;text-transform:uppercase} .lane{fill:var(--lane);stroke:var(--laneline)}
.n-name{font-size:13px;font-weight:600} .n-type{font-size:11px}
.k-app{fill:var(--app);stroke:var(--app-s)} .k-infra{fill:var(--infra);stroke:var(--infra-s)}
.k-net{fill:var(--net);stroke:var(--net-s)} .k-ext{fill:var(--ext);stroke:var(--ext-s)}
.k-team{fill:var(--team);stroke:var(--team-s)}
.edge{fill:none;stroke-width:1.6} .e-calls{stroke:var(--calls)} .e-data{stroke:var(--data)}
.e-dep{stroke:var(--dep);stroke-dasharray:5 4} .e-run{stroke:var(--run);stroke-dasharray:2 3}
.e-route{stroke:var(--route)} .e-own{stroke:var(--own)}
.a-calls{fill:var(--calls)} .a-data{fill:var(--data)} .a-dep{fill:var(--dep)} .a-run{fill:var(--run)}
.a-route{fill:var(--route)} .a-own{fill:var(--own)}
.chip{fill:var(--chip);stroke:var(--laneline)} .lbl{font-size:10.5px} .lbl-k{font-size:9.5px;font-weight:600}
.helm{fill:none;stroke:var(--muted);stroke-dasharray:6 4} .helm-t{font-size:11px;font-style:italic}
.small{font-size:11px} .halo{paint-order:stroke;stroke:var(--lane);stroke-width:5px;stroke-linejoin:round}
"""


def text_w(s, size):
    """Rough text width for a sans-serif font, enough to size chips and avoid collisions."""
    return sum(0.62 if c.isupper() or c in "mwMW" else 0.33 if c in "il.,:;|!/ '" else 0.54
               for c in s) * size


def short(s):
    return (s.replace("oidc auth code + pkce", "OIDC PKCE")
             .replace("oidc client credentials", "OIDC client creds"))


def edge_label(e):
    """Kind plus the attributes worth reading on a diagram, e.g. 'calls' / 'HTTPS 443 /api/v1'."""
    a = e["attributes"]
    parts = []
    if "flow" in a:
        parts.append(short(a["flow"]))
    elif a.get("purpose") == "jwks":
        parts.append("JWKS")
    elif str(a.get("purpose", "")).startswith("otlp"):
        parts.append("OTLP")
    proto = a.get("protocol")
    if proto:
        parts.append({"grpc": "gRPC", "pgx": "pgx"}.get(proto, proto.upper()))
    if "port" in a and e["type"] != "routes_via":
        parts.append(str(a["port"]))
    path = a.get("path")
    if path and len(path) > 18:
        path = path.split("/")[0] + "/…/" + path.rsplit("/", 1)[-1]
    if path and not ("flow" in a or a.get("purpose") == "jwks"):
        parts.append(path)
    if "payload" in a:
        parts.append(f"({a['payload'].upper()})")
    if "role" in a and e["type"] == "stores_data_in":
        parts.append("as " + a["role"])
    if not parts:
        for k in ("contract", "purpose", "workload", "entry", "role"):
            if k in a:
                parts.append(a[k])
                break
    return e["type"], " ".join(parts)


def main():
    g = json.loads(SRC.read_text())
    nodes = {n["id"]: n for n in g["nodes"]}
    edges = g["edges"]
    lanes = {k: [] for k in LANES}
    for n in sorted(g["nodes"], key=lambda n: (n["kind"], n["type"], n["id"])):
        lanes[lane_of(n)].append(n["id"])
    nbrs = {i: [] for i in nodes}
    for e in edges:
        nbrs[e["from"]].append(e["to"])
        nbrs[e["to"]].append(e["from"])

    pos = {}  # id -> (cx, cy)

    def place_row(lane):
        ids = lanes[lane]
        y = LANES[lane][1]
        span = (MAIN_X1 - MAIN_X0) / max(len(ids), 1)
        for i, nid in enumerate(ids):
            pos[nid] = (MAIN_X0 + span * (i + 0.5), y)

    def place_side():
        ids = lanes["build"]
        top = LANES["apps"][1]
        for i, nid in enumerate(ids):
            pos[nid] = ((SIDE_X0 + SIDE_X1) / 2, top + SIDE_STEP * i)

    def place(lane):
        place_side() if lane == "build" else place_row(lane)

    rows = ["clients", "apps", "platform"]
    for lane in rows + ["build"]:
        place(lane)

    # Order each lane by trying every permutation (lanes are small): shortest total edge run,
    # and a heavy penalty for an edge between two nodes of a row that are not side by side.
    def cost(lane):
        c = 0.0
        members = lanes[lane]
        for e in edges:
            a, b = e["from"], e["to"]
            if a not in pos or b not in pos or (a not in members and b not in members):
                continue
            if a in members and b in members:
                c += 2000 * (abs(members.index(a) - members.index(b)) - 1)
            else:
                c += abs(pos[a][0] - pos[b][0]) + abs(pos[a][1] - pos[b][1]) * 0.3
        return c

    for _ in range(4):
        for lane in rows + ["build"]:
            best = None
            for perm in permutations(sorted(lanes[lane])):
                lanes[lane] = list(perm)
                place(lane)
                c = cost(lane)
                if best is None or c < best[0] - 1e-6:
                    best = (c, list(perm))
            lanes[lane] = best[1]
            place(lane)

    out = []
    add = out.append
    side_top = LANES["apps"][1] - 64
    side_bot = LANES["apps"][1] + SIDE_STEP * max(len(lanes["build"]) - 1, 0) + NODE_H / 2 + 16
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-labelledby="t d">')
    add(f"<title id=\"t\">Architecture E2E — {escape(g['environment'])} architecture</title>")
    add(f'<desc id="d">{len(nodes)} nodes and {len(edges)} edges from GET /api/v1/graph.</desc>')
    add(f"<style>{STYLE}</style>")
    add(f'<rect class="bg" width="{W}" height="{H}"/>')
    add('<text class="t title" x="40" y="44">Architecture E2E — how the product is built and deployed</text>')
    add(f'<text class="m sub" x="40" y="66">Environment <tspan font-weight="600">{escape(g["environment"])}</tspan>'
        f" · {len(nodes)} nodes · {len(edges)} edges · modelled in the product itself through its own write API</text>")

    # Lane backgrounds and titles (titles are drawn over the edges, see `late`).
    late = []
    for lane in rows:
        y = LANES[lane][1]
        add(f'<rect class="lane" x="20" y="{y - 64}" width="{MAIN_X1 - MAIN_X0 + 40}" '
            f'height="{64 + NODE_H / 2 + 14}" rx="10"/>')
        late.append(f'<text class="m lane-t halo" x="34" y="{y - 46}">{escape(LANES[lane][0])}</text>')
    add(f'<rect class="lane" x="{SIDE_X0 - 20}" y="{side_top}" width="{SIDE_X1 - SIDE_X0 + 40}" '
        f'height="{side_bot - side_top}" rx="10"/>')
    add(f'<text class="m lane-t" x="{SIDE_X0 - 6}" y="{side_top + 18}">{escape(LANES["build"][0])}</text>')

    taken = []  # label boxes placed so far

    # Network band: each network node is a stretch of the band; routes_via edges into it are listed.
    net = lanes["network"]
    band_y = LANES["network"][1]
    band_rects = []
    if net:
        span = (MAIN_X1 - MAIN_X0 + 40) / len(net)
        for i, nid in enumerate(net):
            n = nodes[nid]
            x0 = 20 + span * i
            band_rects.append((x0, band_y - 26, x0 + span, band_y + 26))
            add(f'<rect class="{KIND_CLASS[n["kind"]]}" x="{x0 + 4}" y="{band_y - 26}" width="{span - 8}" '
                f'height="52" rx="10" fill-opacity="0.55" stroke-width="1.2"/>')
            add(f'<text class="t n-name" x="{x0 + 16}" y="{band_y - 6}"><tspan class="m lane-t">'
                f'{escape(LANES["network"][0])}</tspan><tspan dx="10">{escape(n["name"])}</tspan>'
                f'<tspan class="m n-type" font-weight="400" dx="8">{n["kind"]} · {escape(n["type"])}</tspan></text>')
            via = [e for e in edges if e["type"] == "routes_via" and e["to"] == nid]
            if via:
                names = ", ".join(nodes[e["from"]]["name"] for e in via)
                add(f'<text class="m small" x="{x0 + 16}" y="{band_y + 14}">'
                    f'<tspan font-weight="600">routes_via ←</tspan> {escape(names)}</text>')

    # Helm releases: a dashed box around the nodes tagged helm:<release>.
    release_of, helm_box, helm_chips = {}, {}, []
    for nid, n in nodes.items():
        for t in n["tags"]:
            if t.startswith("helm:") and nid in pos:
                release_of[nid] = t[5:]
    for rel in sorted(set(release_of.values())):
        ids = [i for i, r in release_of.items() if r == rel]
        xs, ys = [pos[i][0] for i in ids], [pos[i][1] for i in ids]
        box = (min(xs) - NODE_W / 2 - 14, min(ys) - NODE_H / 2 - 9, max(xs) + NODE_W / 2 + 14,
               max(ys) + NODE_H / 2 + 9)
        helm_box[rel] = box
        add(f'<rect class="helm" x="{box[0]}" y="{box[1]}" width="{box[2] - box[0]}" '
            f'height="{box[3] - box[1]}" rx="8"/>')
        label = f"Helm release “{rel}”"
        w = text_w(label, 11) + 14
        chip = (box[2] - 12 - w, box[1] - 9, box[2] - 12, box[1] + 9)
        taken.append(chip)
        helm_chips.append(f'<rect class="chip" x="{chip[0]:.1f}" y="{chip[1]}" width="{w:.1f}" height="18" rx="9"/>'
                          f'<text class="m helm-t" x="{chip[0] + 7:.1f}" y="{chip[1] + 13}">{escape(label)}</text>')

    # Links to draw. routes_via edges into the band are listed in it. Edges of the same type from
    # every workload of a Helm release to one build & deploy node become one link from the box.
    links = []
    groups = {}
    for e in edges:
        if e["type"] == "routes_via" and e["to"] in net:
            continue
        rel = release_of.get(e["from"])
        if rel and lane_of(nodes[e["to"]]) == "build":
            groups.setdefault((rel, e["type"], e["to"]), []).append(e)
        else:
            links.append({"from": e["from"], "to": e["to"], "type": e["type"], "label": edge_label(e)})
    for (rel, typ, to), es in sorted(groups.items()):
        if len(es) == 1:
            e = es[0]
            links.append({"from": e["from"], "to": to, "type": typ, "label": edge_label(e)})
            continue
        details = sorted({edge_label(e)[1] for e in es})
        links.append({"from": "helm:" + rel, "to": to, "type": typ,
                      "label": (f"{typ} ×{len(es)}", " / ".join(details))})

    def center(ref):
        if ref.startswith("helm:"):
            b = helm_box[ref[5:]]
            return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
        return pos[ref]

    def in_build(ref):
        return not ref.startswith("helm:") and lane_of(nodes[ref]) == "build"

    def side(ref, other):
        (x, y), (ox, oy) = center(ref), center(other)
        if ref.startswith("helm:"):
            return "right"
        if in_build(ref) != in_build(other):
            if in_build(ref):
                return "left"
            row = lanes[lane_of(nodes[ref])]
            return "right" if row[-1] == ref else "bottom"
        if in_build(ref):
            return "bottom" if oy > y else "top"
        if abs(oy - y) < 1:
            return "right" if ox > x else "left"
        return "bottom" if oy > y else "top"

    ends = {}
    for i, l in enumerate(links):
        ends.setdefault((l["from"], side(l["from"], l["to"])), []).append((i, l["to"]))
        ends.setdefault((l["to"], side(l["to"], l["from"])), []).append((i, l["from"]))
    anchor = {}
    for (ref, s), lst in ends.items():
        x, y = center(ref)
        if ref.startswith("helm:"):
            b = helm_box[ref[5:]]
            half_w, half_h = (b[2] - b[0]) / 2, (b[3] - b[1]) / 2
        else:
            half_w, half_h = NODE_W / 2, NODE_H / 2
        horiz = s in ("top", "bottom")
        lst.sort(key=lambda t: center(t[1])[0 if horiz else 1])
        for j, (i, _) in enumerate(lst):
            f = (j + 1) / (len(lst) + 1) - 0.5
            anchor[(i, ref)] = ({"top": (x + f * (2 * half_w - 30), y - half_h),
                                 "bottom": (x + f * (2 * half_w - 30), y + half_h),
                                 "left": (x - half_w, y + f * (2 * half_h - 16)),
                                 "right": (x + half_w, y + f * (2 * half_h - 16))}[s], s)

    # A link that jumps over a row passes through a gap between that row's boxes.
    row_y = {lane: LANES[lane][1] for lane in rows}
    gaps = {}
    for lane in rows:
        xs = sorted(pos[i][0] for i in lanes[lane])
        edges_x = [20] + [v for x in xs for v in (x - NODE_W / 2, x + NODE_W / 2)] + [MAIN_X1 + 20]
        gaps[lane] = [(edges_x[k], edges_x[k + 1]) for k in range(0, len(edges_x), 2)]
    via = {}
    for i, l in enumerate(links):
        if l["from"].startswith("helm:") or in_build(l["from"]) or in_build(l["to"]):
            continue
        y0, y1 = pos[l["from"]][1], pos[l["to"]][1]
        for lane in rows:
            if min(y0, y1) + 1 < row_y[lane] < max(y0, y1) - 1:
                t = (row_y[lane] - y0) / (y1 - y0)
                ideal = pos[l["from"]][0] + t * (pos[l["to"]][0] - pos[l["from"]][0])
                g_i = min(range(len(gaps[lane])),
                          key=lambda k: abs((gaps[lane][k][0] + gaps[lane][k][1]) / 2 - ideal))
                via.setdefault((lane, g_i), []).append((ideal, i))
    waypoint = {}
    for (lane, g_i), lst in via.items():
        lo, hi = gaps[lane][g_i]
        lst.sort()
        for j, (_, i) in enumerate(lst):
            waypoint[i] = (lo + (hi - lo) * (j + 1) / (len(lst) + 1), row_y[lane])

    boxes = [(pos[n][0] - NODE_W / 2, pos[n][1] - NODE_H / 2, pos[n][0] + NODE_W / 2, pos[n][1] + NODE_H / 2)
             for n in pos]

    def overlaps(b, others, pad=3):
        return any(b[0] < o[2] + pad and b[2] + pad > o[0] and b[1] < o[3] + pad and b[3] + pad > o[1]
                   for o in others)

    def bez(seg, t):
        p0, c0, c1, p1 = seg
        u = 1 - t
        return tuple(u**3 * p0[k] + 3 * u * u * t * c0[k] + 3 * u * t * t * c1[k] + t**3 * p1[k] for k in (0, 1))

    def ctrl(p, s, d):
        return {"top": (p[0], p[1] - d), "bottom": (p[0], p[1] + d),
                "left": (p[0] - d, p[1]), "right": (p[0] + d, p[1])}[s]

    curves, labels = [], []
    for i, l in enumerate(links):
        (p0, s0), (p1, s1) = anchor[(i, l["from"])], anchor[(i, l["to"])]
        if i in waypoint:
            w = waypoint[i]
            d0, d1 = abs(w[1] - p0[1]) * 0.5, abs(p1[1] - w[1]) * 0.5
            segs = [(p0, ctrl(p0, s0, d0), (w[0], w[1] - d0), w), (w, (w[0], w[1] + d1), ctrl(p1, s1, d1), p1)]
        else:
            d = max(abs(p1[1] - p0[1]), abs(p1[0] - p0[0])) * 0.45 + 20
            segs = [(p0, ctrl(p0, s0, d), ctrl(p1, s1, d), p1)]
        cls = EDGE_CLASS.get(l["type"], "e-dep")
        path = f"M{p0[0]:.1f},{p0[1]:.1f}" + "".join(
            f" C{c0[0]:.1f},{c0[1]:.1f} {c1[0]:.1f},{c1[1]:.1f} {q[0]:.1f},{q[1]:.1f}" for _, c0, c1, q in segs)
        curves.append(f'<path class="edge {cls}" d="{path}" marker-end="url(#m-{cls[2:]})"/>')
        kind, detail = l["label"]
        w_ = text_w(kind, 9.5) + text_w(detail, 10.5) + (17 if detail else 12)
        h = 17
        cands = [(seg, t) for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.22, 0.78, 0.15, 0.85) for seg in segs]
        b = None
        for seg, t in cands:
            cx, cy = bez(seg, t)
            cand = (cx - w_ / 2, cy - h / 2, cx + w_ / 2, cy + h / 2)
            if not (overlaps(cand, taken) or overlaps(cand, boxes) or overlaps(cand, band_rects, 0)):
                b = cand
                break
        if b is None:
            cx, cy = bez(segs[-1], 0.5)
            for dy in (0, 14, -14, 28, -28, 42, -42, 52, -52):
                for dx in (0, -40, 40, -80, 80, -120, 120, -160):
                    cand = (cx - w_ / 2 + dx, cy - h / 2 + dy, cx + w_ / 2 + dx, cy + h / 2 + dy)
                    if b is None and not (overlaps(cand, taken) or overlaps(cand, boxes)):
                        b = cand
            b = b or (cx - w_ / 2, cy - h / 2, cx + w_ / 2, cy + h / 2)
        taken.append(b)
        lab = [f'<rect class="chip" x="{b[0]:.1f}" y="{b[1]:.1f}" width="{w_:.1f}" height="{h}" rx="8.5"/>',
               f'<text x="{b[0] + 6:.1f}" y="{b[1] + 12:.1f}"><tspan class="lbl-k a-{cls[2:]}">{escape(kind)}</tspan>']
        if detail:
            lab.append(f'<tspan class="t lbl" dx="5">{escape(detail)}</tspan>')
        lab.append("</text>")
        labels.append("".join(lab))

    add("<defs>")
    for c in sorted(set(EDGE_CLASS.values())):
        add(f'<marker id="m-{c[2:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path class="a-{c[2:]}" d="M0,0 L10,5 L0,10 z"/></marker>')
    add("</defs>")
    out.extend(curves)

    for nid, (x, y) in pos.items():
        n = nodes[nid]
        add(f'<rect class="{KIND_CLASS[n["kind"]]}" x="{x - NODE_W / 2:.1f}" y="{y - NODE_H / 2:.1f}" '
            f'width="{NODE_W}" height="{NODE_H}" rx="9" stroke-width="1.4"/>')
        add(f'<text class="t n-name" x="{x:.1f}" y="{y - 3:.1f}" text-anchor="middle">{escape(n["name"])}</text>')
        add(f'<text class="m n-type" x="{x:.1f}" y="{y + 15:.1f}" text-anchor="middle">'
            f'{escape(n["kind"])} · {escape(n["type"])}</text>')
    out.extend(late)
    out.extend(labels)
    out.extend(helm_chips)

    # Legend and footer.
    ly = H - 92
    add(f'<text class="m lane-t" x="40" y="{ly}">Legend</text>')
    x = 40
    used_kinds = sorted({n["kind"] for n in nodes.values()})
    for k in used_kinds:
        add(f'<rect class="{KIND_CLASS[k]}" x="{x}" y="{ly + 12}" width="22" height="14" rx="4" stroke-width="1.2"/>')
        add(f'<text class="t small" x="{x + 28}" y="{ly + 23}">{k}</text>')
        x += 36 + text_w(k, 11)
    x += 10
    for t in [t for t in EDGE_CLASS if any(lk["type"] == t for lk in links)]:
        c = EDGE_CLASS[t]
        add(f'<path class="edge {c}" d="M{x},{ly + 19} h30" marker-end="url(#m-{c[2:]})"/>')
        add(f'<text class="t small" x="{x + 38}" y="{ly + 23}">{t}</text>')
        x += 50 + text_w(t, 11)
    add(f'<rect class="helm" x="{x}" y="{ly + 11}" width="26" height="16" rx="4"/>'
        f'<text class="t small" x="{x + 32}" y="{ly + 23}">Helm release (tag helm:&lt;name&gt;)</text>')
    add(f'<text class="m small" x="40" y="{ly + 48}">Owner of every node: team '
        f'{escape(", ".join(sorted({n["owner"] for n in nodes.values()})))}. Edge chips: edge type, then its key '
        f'attributes (protocol, port, path, auth flow, database role).</text>')
    add(f'<text class="m small" x="40" y="{H - 18}">Generated from Architecture E2E\'s own model '
        f'(GET /api/v1/graph) by docs/architecture/render.py</text>')
    add("</svg>")
    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT} ({len(nodes)} nodes, {len(edges)} edges)")


if __name__ == "__main__":
    main()

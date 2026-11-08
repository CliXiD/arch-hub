# Spec 005: landscape-view

> Status: Draft · Implements: [BR-020], [BR-022], [BR-023], [NFR-005], [NFR-006] · Decisions: [ADR-0007]
> Repos: arch-web, arch-api · Last reviewed: 2026-11-08

## Summary

The home screen: an interactive graph of one environment's whole model, with search, filters,
optional layers and export. It is the entry point to the focus and impact views.

## Behaviour

- **SPEC-landscape-view-01** `/` (or `/landscape?env=prod`) renders every node and edge of the chosen environment (defaulting to the first in the configured order, usually prod) on a pan-and-zoom canvas, with an automatic layered layout from ELK computed in a web worker. Each node shows an icon for its kind, its name, its type and its owner team. Edges are styled by type, and `calls` edges are labelled with protocol and port. [BR-020]
- **SPEC-landscape-view-02** While loading, the canvas shows a skeleton and the text "Loading the landscape…". With no nodes, it shows "Nothing modelled in <env> yet", with links to "Add a node" (for editors) and "Import YAML" (docs). If loading fails, it shows the error and a retry button. [BR-020]
- **SPEC-landscape-view-03** A search box (`/` focuses it) finds nodes by id or name. Choosing a result centres and highlights that node. [BR-020]
- **SPEC-landscape-view-04** Filters for kind, type, owner team and tag hide non-matching nodes and their edges. The filters are kept in the URL query, so a view can be shared with other signed-in users. [BR-020] [NFR-001]
- **SPEC-landscape-view-05** Clicking a node opens a side panel with its details and actions: "Focus" (006), "Impact" (007), and "Edit" (003, if permitted). Double-clicking opens the focus view. [BR-020] [BR-021] [BR-030]
- **SPEC-landscape-view-06** A layer switch shows only the nodes of one layer: business (team), application, infrastructure or network (by kind). Edges between visible nodes stay visible, and edges to hidden nodes are collapsed into a count badge. (Should.) [BR-022]
- **SPEC-landscape-view-07** Export the current view as SVG or PNG, and as Mermaid (`flowchart LR`) or draw.io XML. (Could.) [BR-023]
- **SPEC-landscape-view-08** A "List" toggle shows the same filtered nodes and edges as accessible tables with the same actions, as the canvas alternative required by [NFR-006]. [NFR-006]

## Interfaces

- Reads `GET /api/v1/graph?environment=`, `/types`, `/teams` and `/environments` ([002_model.md]).
- Route: `/landscape?env=&kind=&type=&owner=&tag=&layer=&q=`.

## Data

- None owned. The graph is cached by TanStack Query per environment and refetched on window focus.

## Non-functional

- [NFR-005]: 2,000 nodes and 10,000 edges render and become interactive in under 3 s on a mid-range laptop. Beyond 500 visible nodes, labels show only past a zoom threshold.
- [NFR-006]: the canvas can be used from the keyboard (tab between nodes, Enter opens the panel), and the side panel and list view meet WCAG 2.1 AA.

## Open questions

- None.

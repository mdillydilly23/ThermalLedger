# ADR-005 — Map Provider: MapLibre GL JS + Deck.gl HeatmapLayer

**Status:** Accepted  
**Date:** Pre-development

## Context

The execution plan calls for:
1. An interactive facility map with EVS-coded markers (Permian Basin)
2. An animated CH₄ column heat map overlay (plume visualization)

Two viable combinations exist:

| Option | Base Map | Cost | Rate Limits | Risk |
|--------|----------|------|-------------|------|
| Mapbox GL JS + Deck.gl | Mapbox tiles | Free tier: 50k loads/mo | Yes | Rate-limited during demo if free tier exceeded |
| **MapLibre GL JS + Deck.gl** | **CARTO free tiles or OpenStreetMap** | **$0, unlimited** | **None** | **None** |

MapLibre GL JS is a fully open-source, drop-in replacement for Mapbox GL JS. The API is identical — switching between them requires only a one-line import change.

## Decision

- **MapLibre GL JS** as the base map renderer (`maplibre-gl` npm package).
- **`react-map-gl`** (MapLibre flavor) as the React wrapper — `<Map>` component.
- **Deck.gl `HeatmapLayer`** for the CH₄ plume overlay on top of the base map.
- **Tile source:** CARTO free tiles (`https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json`) — dark basemap makes the green/amber/red EVS markers pop visually.
- Facility markers rendered as Deck.gl `ScatterplotLayer` — color-mapped to EVS flag (`clear`=green, `watch`=amber, `high`=red).

## Consequences

- Zero map API cost. Zero rate limit risk during demo.
- No Mapbox token required — one fewer secret in `.env`.
- If a judge asks to switch tile style live, it's a one-line config change.
- MapLibre and Mapbox GL JS share the same style spec — any Mapbox style URL also works with MapLibre.

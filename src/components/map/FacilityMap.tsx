/**
 * FacilityMap — main map component.
 * ADR-005: MapLibre GL JS base map + Deck.gl ScatterplotLayer (EVS markers) + HeatmapLayer (CH4 plume).
 * Zero Mapbox token required.
 */

import { Map } from 'react-map-gl/maplibre'
import { DeckGL } from '@deck.gl/react'
import { ScatterplotLayer } from '@deck.gl/layers'
import { HeatmapLayer } from '@deck.gl/aggregation-layers'
import type { FacilitySummary } from '../../types/evs'
import { evsFlagToRGB } from '../../types/evs'

// ADR-005: CARTO dark-matter tiles — free, unlimited, visually strong for EVS color coding
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

const INITIAL_VIEW = {
  longitude: -103.0,   // Permian Basin, Texas
  latitude: 31.5,
  zoom: 7,
  pitch: 0,
  bearing: 0,
}

interface Props {
  facilities: FacilitySummary[]
  plumePoints: { position: [number, number]; weight: number }[]
  onFacilityClick: (facilityId: string) => void
}

export function FacilityMap({ facilities, plumePoints, onFacilityClick }: Props) {
  const facilityLayer = new ScatterplotLayer({
    id: 'facilities',
    data: facilities,
    getPosition: (f) => [f.longitude, f.latitude],
    getColor: (f) => (f.latest_flag ? evsFlagToRGB(f.latest_flag) : [150, 150, 150]),
    getRadius: 8000,           // metres
    radiusMinPixels: 6,
    radiusMaxPixels: 18,
    pickable: true,
    onClick: ({ object }) => object && onFacilityClick(object.facility_id),
  })

  // ADR-005: HeatmapLayer for CH4 plume overlay
  const plumeLayer = new HeatmapLayer({
    id: 'ch4-plume',
    data: plumePoints,
    getPosition: (d: { position: [number, number]; weight: number }) => d.position,
    getWeight: (d: { position: [number, number]; weight: number }) => d.weight,
    radiusPixels: 40,
    intensity: 1,
    threshold: 0.03,
    colorRange: [
      [0, 0, 255, 0],
      [0, 128, 255, 80],
      [0, 255, 128, 140],
      [128, 255, 0, 180],
      [255, 200, 0, 220],
      [255, 60, 0, 255],
    ],
  })

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW}
      controller={true}
      layers={[plumeLayer, facilityLayer]}
      style={{ width: '100%', height: '100%' }}
    >
      <Map mapStyle={MAP_STYLE} />
    </DeckGL>
  )
}

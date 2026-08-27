/**
 * DashboardPage — full-height split: map on left, detail panel on right.
 * Fetches facility list with React Query, passes to FacilityMap.
 * Clicking a marker loads the EVS detail panel.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FacilityMap } from '../components/map/FacilityMap'
import { FacilityPanel } from '../components/dashboard/FacilityPanel'
import { fetchFacilities, fetchPlumeGeoJSON } from '../lib/api'

export function DashboardPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['facilities'],
    queryFn: fetchFacilities,
  })

  const facilities = data?.facilities ?? []
  const plumeQuery = useQuery({
    queryKey: ['plume', selectedId],
    queryFn: () => fetchPlumeGeoJSON(selectedId!, '2024-06-30'),
    enabled: selectedId !== null,
  })
  const plumePoints = (plumeQuery.data?.geojson.features ?? []).map((feature) => ({
    position: feature.geometry.coordinates,
    weight: feature.properties.weight,
  }))
  const plumeSource = plumeQuery.data?.cached === false
    ? `${plumeQuery.data.source.replace(/_/g, ' ')} (${plumeQuery.data.observation_date})`
    : 'deterministic demo fixture (not a live satellite retrieval)'

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* ── Map ─────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative' }}>
        {isLoading && <LoadingOverlay message="Loading facilities…" />}
        {isError && <LoadingOverlay message="Failed to load facilities." error />}
        <FacilityMap
          facilities={facilities}
          plumePoints={plumePoints}
          onFacilityClick={setSelectedId}
        />
        <div style={{
          position: 'absolute', left: '12px', bottom: '12px', zIndex: 2,
          padding: '7px 10px', borderRadius: '6px', background: 'rgba(15,17,23,0.88)',
          border: '1px solid #2d3148', color: '#94a3b8', fontSize: '11px',
        }}>
          {selectedId
            ? `Plume overlay: ${plumeSource}`
            : 'Select a facility to view its verification overlay'}
        </div>
      </div>

      {/* ── Detail panel ────────────────────────────────────── */}
      <div
        style={{
          width: selectedId ? '360px' : '0',
          overflow: 'hidden',
          transition: 'width 0.2s ease',
          borderLeft: '1px solid #2d3148',
          background: '#1a1d27',
          flexShrink: 0,
        }}
      >
        {selectedId && (
          <FacilityPanel
            facilityId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  )
}

function LoadingOverlay({ message, error }: { message: string; error?: boolean }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(15,17,23,0.7)',
        color: error ? '#f87171' : '#94a3b8',
        fontSize: '14px',
        pointerEvents: 'none',
      }}
    >
      {message}
    </div>
  )
}

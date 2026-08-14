/**
 * DashboardPage — full-height split: map on left, detail panel on right.
 * Fetches facility list with React Query, passes to FacilityMap.
 * Clicking a marker loads the EVS detail panel.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FacilityMap } from '../components/map/FacilityMap'
import { FacilityPanel } from '../components/dashboard/FacilityPanel'
import { fetchFacilities } from '../lib/api'

export function DashboardPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['facilities'],
    queryFn: fetchFacilities,
  })

  const facilities = data?.facilities ?? []

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* ── Map ─────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative' }}>
        {isLoading && <LoadingOverlay message="Loading facilities…" />}
        {isError && <LoadingOverlay message="Failed to load facilities." error />}
        <FacilityMap
          facilities={facilities}
          plumePoints={[]}
          onFacilityClick={setSelectedId}
        />
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

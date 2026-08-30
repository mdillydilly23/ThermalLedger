/**
 * DashboardPage — full-height split: map on left, detail panel on right.
 * Fetches facility list with React Query, passes to FacilityMap.
 * Clicking a marker loads the EVS detail panel.
 * H-2: accepts initialFacilityId to pre-select a facility from the Upload page.
 * M-1: fleet summary strip below the map showing flag distribution and EVS histogram.
 */

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FacilityMap } from '../components/map/FacilityMap'
import { FacilityPanel } from '../components/dashboard/FacilityPanel'
import { fetchFacilities, fetchPlumeGeoJSON } from '../lib/api'
import type { FacilitySummary } from '../types/evs'

interface Props {
  /** Facility ID to pre-select on mount (from ESG upload navigation). */
  initialFacilityId?: string | null
  /** Called once after the initialFacilityId has been consumed to clear it. */
  onFacilityConsumed?: () => void
}

export function DashboardPage({ initialFacilityId, onFacilityConsumed }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Pre-select facility when arriving from Upload → "View on map"
  useEffect(() => {
    if (initialFacilityId) {
      setSelectedId(initialFacilityId)
      onFacilityConsumed?.()
    }
  }, [initialFacilityId, onFacilityConsumed])

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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ── Map + panel row ──────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
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

      {/* ── Fleet summary strip ──────────────────────────────── */}
      {facilities.length > 0 && <FleetSummary facilities={facilities} onSelect={setSelectedId} />}
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

// ── M-1: Fleet summary strip with flag counts and EVS distribution ────────────

interface FleetSummaryProps {
  facilities: FacilitySummary[]
  onSelect: (id: string) => void
}

function FleetSummary({ facilities, onSelect }: FleetSummaryProps) {
  const scored = facilities.filter((f) => f.latest_evs != null)
  const counts = { high: 0, watch: 0, clear: 0 }
  for (const f of scored) {
    if (f.latest_flag === 'high') counts.high++
    else if (f.latest_flag === 'watch') counts.watch++
    else if (f.latest_flag === 'clear') counts.clear++
  }
  const avgEvs = scored.length > 0
    ? scored.reduce((sum, f) => sum + (f.latest_evs ?? 0), 0) / scored.length
    : null

  // Build 10 buckets 0-10, 10-20, ... 90-100 for EVS histogram
  const buckets = Array.from({ length: 10 }, (_, i) => ({
    label: `${i * 10}`,
    count: scored.filter((f) => {
      const v = f.latest_evs ?? 0
      return i < 9 ? v >= i * 10 && v < (i + 1) * 10 : v >= 90
    }).length,
  }))
  const maxBucket = Math.max(...buckets.map((b) => b.count), 1)

  const BAR_H = 48
  const BAR_W = 18
  const GAP = 4
  const svgWidth = buckets.length * (BAR_W + GAP) - GAP

  return (
    <div style={{
      background: '#13151f',
      borderTop: '1px solid #2d3148',
      padding: '10px 16px',
      display: 'flex',
      alignItems: 'center',
      gap: '24px',
      flexShrink: 0,
      flexWrap: 'wrap',
    }}>
      {/* Flag counts */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Fleet</span>
        {([['high', '#ef4444', 'HIGH'], ['watch', '#f59e0b', 'WATCH'], ['clear', '#22c55e', 'CLEAR']] as const).map(([flag, color, label]) => (
          <div key={flag} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, display: 'inline-block' }} />
            <span style={{ fontSize: '12px', color, fontWeight: 700 }}>{counts[flag]}</span>
            <span style={{ fontSize: '11px', color: '#475569' }}>{label}</span>
          </div>
        ))}
        {avgEvs != null && (
          <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '4px' }}>
            Avg EVS: <strong style={{ color: '#94a3b8' }}>{avgEvs.toFixed(1)}</strong>
          </span>
        )}
      </div>

      {/* EVS distribution histogram (inline SVG) */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px' }}>
        <span style={{ fontSize: '11px', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '2px' }}>EVS dist.</span>
        <svg width={svgWidth} height={BAR_H + 14} style={{ display: 'block', overflow: 'visible' }}>
          {buckets.map((bucket, i) => {
            const barH = bucket.count > 0 ? Math.max(4, Math.round((bucket.count / maxBucket) * BAR_H)) : 2
            const x = i * (BAR_W + GAP)
            const barScore = i * 10 + 5
            const barColor = barScore < 33 ? '#ef4444' : barScore < 66 ? '#f59e0b' : '#22c55e'
            return (
              <g key={i}>
                <rect
                  x={x}
                  y={BAR_H - barH}
                  width={BAR_W}
                  height={barH}
                  fill={barColor}
                  fillOpacity={0.8}
                  rx={2}
                  style={{ cursor: bucket.count > 0 ? 'pointer' : 'default' }}
                  onClick={() => {
                    if (!bucket.count) return
                    const hit = scored.find((f) => {
                      const v = f.latest_evs ?? 0
                      return i < 9 ? v >= i * 10 && v < (i + 1) * 10 : v >= 90
                    })
                    if (hit) onSelect(hit.facility_id)
                  }}
                >
                  <title>{`EVS ${i * 10}–${(i + 1) * 10}: ${bucket.count} facilities`}</title>
                </rect>
                <text x={x + BAR_W / 2} y={BAR_H + 11} textAnchor="middle" fontSize={8} fill="#475569">
                  {bucket.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Facility list summary */}
      <div style={{ fontSize: '11px', color: '#475569', marginLeft: 'auto' }}>
        {scored.length} / {facilities.length} facilities scored
      </div>
    </div>
  )
}

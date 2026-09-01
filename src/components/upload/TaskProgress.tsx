/**
 * TaskProgress — step-by-step progress indicator for background tasks.
 * ADR-001: polls GET /tasks/{taskId} via useTask hook until SUCCESS or FAILURE.
 */

import { useTask } from '../../hooks/useTask'
import type { ESGClaimMatch } from '../../types/evs'

interface Props {
  taskId: string
  label: string
  /** Called when a matched facility is clicked — navigates to dashboard with that facility selected. */
  onNavigateToFacility?: (facilityId: string) => void
}

const STEPS = [
  { stage: 'Queued...', label: 'Queued' },
  { stage: 'Processing...', label: 'Extracting emissions data with Granite' },
  { stage: 'Complete', label: 'Parsing complete' },
]

export function TaskProgress({ taskId, label, onNavigateToFacility }: Props) {
  const task = useTask(taskId)

  if (!task) {
    return <StatusRow color="#64748b" icon="…" text={`${label} — starting…`} />
  }

  if (task.status === 'FAILURE') {
    return <StatusRow color="#f87171" icon="✗" text={`${label} — failed: ${task.error ?? 'unknown error'}`} />
  }

  if (task.status === 'SUCCESS') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {STEPS.map((s, i) => (
          <StatusRow key={i} color="#22c55e" icon="✓" text={s.label} />
        ))}
        {task.result != null && (
          <ParseResult
            result={task.result as Record<string, unknown>}
            onNavigateToFacility={onNavigateToFacility}
          />
        )}
      </div>
    )
  }

  // In progress
  const currentStage = task.progress_stage ?? 'Processing...'
  // Worker tasks can report a more specific stage than the compact demo UI.
  // Treat that as the middle extraction step rather than rendering no active
  // step at all.
  const matchedStep = STEPS.findIndex((s) => s.stage === currentStage)
  const currentIndex = matchedStep === -1 ? 1 : matchedStep

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {STEPS.map((s, i) => {
        const done = i < currentIndex
        const active = i === currentIndex
        return (
          <StatusRow
            key={i}
            color={done ? '#22c55e' : active ? '#60a5fa' : '#475569'}
            icon={done ? '✓' : active ? '⟳' : '○'}
            text={s.label}
            spinning={active}
          />
        )
      })}
    </div>
  )
}

function StatusRow({
  color, icon, text, spinning,
}: { color: string; icon: string; text: string; spinning?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px' }}>
      <span
        style={{
          color,
          width: '16px',
          textAlign: 'center',
          animation: spinning ? 'spin 1s linear infinite' : undefined,
          display: 'inline-block',
        }}
      >
        {icon}
      </span>
      <span style={{ color: '#94a3b8' }}>{text}</span>
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

function ParseResult({
  result,
  onNavigateToFacility,
}: {
  result: Record<string, unknown>
  onNavigateToFacility?: (facilityId: string) => void
}) {
  const claims = result?.claims as unknown[] | undefined
  const matches = result?.matches as ESGClaimMatch[] | undefined
  if (!claims?.length) return null

  return (
    <div style={{
      marginTop: '12px',
      background: '#0f1117',
      border: '1px solid #2d3148',
      borderRadius: '8px',
      padding: '12px',
    }}>
      <div style={{ fontSize: '11px', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px' }}>
        Granite Extracted Claims ({claims.length})
      </div>
      {(claims as Record<string, unknown>[]).map((c, i) => (
        <div key={i} style={{ fontSize: '12px', color: '#94a3b8', paddingBottom: '6px', borderBottom: '1px solid #1a1d27', marginBottom: '6px' }}>
          <strong style={{ color: '#e2e8f0' }}>{String(c.company_name ?? '—')}</strong>{' '}
          ({String(c.reporting_year ?? '—')}) — CH₄:{' '}
          <span style={{ color: '#60a5fa' }}>
            {c.scope1_ch4_tonnes != null ? `${Number(c.scope1_ch4_tonnes).toLocaleString()} t` : '—'}
          </span>
        </div>
      ))}
      {matches?.length ? (
        <div style={{ marginTop: '10px' }}>
          <div style={{ fontSize: '11px', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px' }}>
            Facility Matches
          </div>
          {matches.map((match) => (
            <button
              key={match.facility_id}
              type="button"
              onClick={() => onNavigateToFacility?.(match.facility_id)}
              disabled={!onNavigateToFacility}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                background: onNavigateToFacility ? 'rgba(96, 165, 250, 0.06)' : 'none',
                border: onNavigateToFacility ? '1px solid #1e3a5f' : 'none',
                borderRadius: '5px',
                padding: '6px 8px',
                marginBottom: '4px',
                cursor: onNavigateToFacility ? 'pointer' : 'default',
                color: 'inherit',
              }}
              title={onNavigateToFacility ? `View ${match.facility_name} on the map` : undefined}
            >
              <span style={{ color: '#e2e8f0', fontSize: '12px', fontWeight: 600 }}>{match.facility_name ?? '—'}</span>{' '}
              <span style={{ color: '#60a5fa', fontSize: '12px' }}>
                EVS {match.latest_evs != null ? Number(match.latest_evs).toFixed(1) : '—'}
              </span>{' '}
              <span style={{ color: '#64748b', fontSize: '12px' }}>{match.latest_flag ?? 'unscored'}</span>
              {onNavigateToFacility && (
                <span style={{ color: '#3b82f6', fontSize: '11px', marginLeft: '6px' }}>→ View on map</span>
              )}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

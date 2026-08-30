/**
 * FacilityPanel — EVS detail panel shown when a map marker is clicked.
 * Fetches full EVSScore for the selected facility.
 * ADR-003: all fields from the shared EVSScore schema.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchFacilityDetail, generateReport } from '../../lib/api'
import { useTask } from '../../hooks/useTask'
import type { EVSScore, DiscrepancyFlag } from '../../types/evs'

interface Props {
  facilityId: string
  onClose: () => void
}

export function FacilityPanel({ facilityId, onClose }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['facility', facilityId],
    queryFn: () => fetchFacilityDetail(facilityId),
  })

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#94a3b8' }}>Facility Detail</span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '18px', lineHeight: 1 }}
          aria-label="Close panel"
        >
          ×
        </button>
      </div>

      {isLoading && <p style={{ color: '#64748b', fontSize: '13px' }}>Loading…</p>}
      {isError && <p style={{ color: '#f87171', fontSize: '13px' }}>Failed to load facility.</p>}
      {data && <EVSDetail score={data} />}
    </div>
  )
}

function EVSDetail({ score }: { score: EVSScore }) {
  const flagColor = score.flag === 'high' ? '#ef4444' : score.flag === 'watch' ? '#f59e0b' : '#22c55e'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div>
        <h2 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '2px' }}>{score.facility_name}</h2>
        <span style={{ fontSize: '11px', color: '#64748b' }}>{score.facility_id}</span>
      </div>

      {/* EVS Score badge */}
      <div style={{
        background: '#0f1117',
        border: `2px solid ${flagColor}`,
        borderRadius: '10px',
        padding: '14px',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: '36px', fontWeight: 800, color: flagColor, lineHeight: 1 }}>
          {score.evs.toFixed(1)}
        </div>
        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>Emission Verification Score</div>
        <FlagBadge flag={score.flag} />
      </div>

      {/* Key metrics */}
      <Section title="Observation Window">
        <Row label="Start" value={score.observation_start} />
        <Row label="End" value={score.observation_end} />
        <Row label="Coverage" value={`${score.coverage_pct.toFixed(1)}% (${score.days_with_valid_retrievals}/${score.total_days > 0 ? score.total_days : Math.round(score.coverage_pct > 0 ? score.days_with_valid_retrievals / (score.coverage_pct / 100) : 0)} days)`} />
      </Section>

      <Section title="Satellite Estimate (CH₄ t/yr)">
        <Row label="Estimate" value={score.satellite_ch4_estimate.toLocaleString()} />
        <Row label="95% CI low" value={score.satellite_uncertainty_low.toLocaleString()} />
        <Row label="95% CI high" value={score.satellite_uncertainty_high.toLocaleString()} />
      </Section>

      <Section title="Reported Value">
        <Row label="CH₄ (t/yr)" value={score.reported_ch4 != null ? score.reported_ch4.toLocaleString() : '—'} />
        <Row label="Source" value={score.reported_source ?? '—'} />
        <Row label="Year" value={score.reported_year?.toString() ?? '—'} />
      </Section>

      <Section title="Discrepancy">
        <Row
          label="Delta"
          value={score.delta_pct != null ? `${score.delta_pct > 0 ? '+' : ''}${score.delta_pct.toFixed(1)}%` : '—'}
          highlight={score.delta_pct != null && score.delta_pct > 20}
        />
        <Row
          label="Sigma deviation"
          value={score.sigma_deviation != null ? score.sigma_deviation.toFixed(2) : '—'}
        />
      </Section>

      <VerificationReport score={score} />

      {/* Blockchain anchor */}
      <div style={{ fontSize: '11px', color: '#475569', borderTop: '1px solid #2d3148', paddingTop: '10px' }}>
        {score.blockchain_tx_id
          ? <>{score.blockchain_tx_id.startsWith('local_') ? 'Local audit anchor: ' : 'Fabric anchor: '}<span style={{ color: '#60a5fa', wordBreak: 'break-all' }}>{score.blockchain_tx_id}</span></>
          : 'Not yet anchored to Hyperledger Fabric.'}
      </div>
    </div>
  )
}

function VerificationReport({ score }: { score: EVSScore }) {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [requestError, setRequestError] = useState<string | null>(null)
  const task = useTask(taskId)
  const result = task?.result as { report_html?: string; cached?: boolean; blockchain_tx_id?: string; audit_mode?: string } | null

  const requestReport = async () => {
    setRequestError(null)
    try {
      const response = await generateReport(
        score.facility_id,
        score.observation_start,
        score.observation_end,
      )
      setTaskId(response.task_id)
    } catch (error: unknown) {
      setRequestError(error instanceof Error ? error.message : 'Unable to start report generation.')
    }
  }

  return (
    <Section title="Verification Report">
      <div style={{ padding: '10px' }}>
        {!taskId && (
          <button
            type="button"
            onClick={requestReport}
            style={reportButtonStyle}
          >
            Generate verification report
          </button>
        )}
        {requestError && <p style={{ marginTop: '8px', color: '#f87171', fontSize: '11px' }}>{requestError}</p>}
        {taskId && !task && <p style={reportStatusStyle}>Queueing report…</p>}
        {task && task.status !== 'SUCCESS' && task.status !== 'FAILURE' && (
          <p style={reportStatusStyle}>{task.progress_stage ?? 'Generating report…'}</p>
        )}
        {task?.status === 'FAILURE' && <p style={{ ...reportStatusStyle, color: '#f87171' }}>{task.error ?? 'Report generation failed.'}</p>}
        {result?.report_html && (
          <>
            <p style={{ ...reportStatusStyle, color: '#4ade80' }}>
              {result.cached ? 'Cached demonstration report ready.' : 'Verification report ready.'}
            </p>
            {result.blockchain_tx_id && (
              <p style={reportStatusStyle}>
                {result.audit_mode === 'local_audit_fallback' ? 'Local audit fallback: ' : 'Audit anchor: '}
                <span style={{ color: '#60a5fa', wordBreak: 'break-all' }}>{result.blockchain_tx_id}</span>
              </p>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '4px' }}>
              <button
                type="button"
                onClick={() => {
                  const blob = new Blob([result.report_html!], { type: 'text/html' })
                  window.open(URL.createObjectURL(blob))
                }}
                style={{ background: 'none', border: 'none', color: '#60a5fa', cursor: 'pointer', fontSize: '11px', textDecoration: 'underline', padding: 0 }}
              >
                Open full report ↗
              </button>
            </div>
            <iframe
              title={`Verification report for ${score.facility_name}`}
              srcDoc={result.report_html}
              sandbox=""
              style={{ width: '100%', height: '420px', border: '1px solid #2d3148', borderRadius: '5px', background: '#fff' }}
            />
          </>
        )}
      </div>
    </Section>
  )
}

const reportButtonStyle: React.CSSProperties = {
  width: '100%', border: '1px solid #2563eb', borderRadius: '6px', padding: '7px 9px',
  background: '#1d4ed8', color: '#eff6ff', cursor: 'pointer', fontSize: '11px', fontWeight: 600,
}

const reportStatusStyle: React.CSSProperties = { marginTop: '8px', color: '#94a3b8', fontSize: '11px' }

function FlagBadge({ flag }: { flag: DiscrepancyFlag }) {
  const colors: Record<DiscrepancyFlag, { bg: string; text: string }> = {
    clear: { bg: '#14532d', text: '#4ade80' },
    watch: { bg: '#78350f', text: '#fbbf24' },
    high:  { bg: '#7f1d1d', text: '#fca5a5' },
  }
  const label: Record<DiscrepancyFlag, string> = {
    clear: 'CLEAR — Within tolerance',
    watch: 'WATCH — Possible under-reporting',
    high:  'HIGH — Significant discrepancy',
  }
  const c = colors[flag]
  return (
    <div style={{
      display: 'inline-block',
      marginTop: '8px',
      padding: '3px 10px',
      borderRadius: '20px',
      background: c.bg,
      color: c.text,
      fontSize: '11px',
      fontWeight: 600,
      letterSpacing: '0.03em',
    }}>
      {label[flag]}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: '11px', fontWeight: 600, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '6px' }}>
        {title}
      </div>
      <div style={{ background: '#0f1117', borderRadius: '8px', overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  )
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      padding: '6px 10px',
      fontSize: '12px',
      borderBottom: '1px solid #1a1d27',
    }}>
      <span style={{ color: '#64748b' }}>{label}</span>
      <span style={{ color: highlight ? '#f87171' : '#e2e8f0', fontWeight: highlight ? 600 : 400 }}>{value}</span>
    </div>
  )
}

/**
 * FacilityPanel — EVS detail panel shown when a map marker is clicked.
 * Fetches full EVSScore for the selected facility.
 * ADR-003: all fields from the shared EVSScore schema.
 *
 * E-1: Granite "Explain this EVS score" chat widget.
 * E-2: EVS trend chart showing score history across observation windows.
 */

import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchFacilityDetail,
  fetchFacilityHistory,
  generateReport,
  explainFacilityEvs,
} from '../../lib/api'
import type { EVSHistoryPoint } from '../../lib/api'
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

      {/* E-2: EVS trend chart */}
      <EVSTrendChart facilityId={score.facility_id} />

      <VerificationReport score={score} />

      {/* E-1: Granite explain chat widget */}
      <GraniteExplainWidget facilityId={score.facility_id} facilityName={score.facility_name} />

      {/* Blockchain anchor */}
      <div style={{ fontSize: '11px', color: '#475569', borderTop: '1px solid #2d3148', paddingTop: '10px' }}>
        {score.blockchain_tx_id
          ? <>{score.blockchain_tx_id.startsWith('local_') ? 'Local audit anchor: ' : 'Fabric anchor: '}<span style={{ color: '#60a5fa', wordBreak: 'break-all' }}>{score.blockchain_tx_id}</span></>
          : 'Not yet anchored to Hyperledger Fabric.'}
      </div>
    </div>
  )
}

// ── E-2: EVS Trend Chart ──────────────────────────────────────────────────────

function EVSTrendChart({ facilityId }: { facilityId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['facility-history', facilityId],
    queryFn: () => fetchFacilityHistory(facilityId),
  })

  if (isLoading) {
    return (
      <Section title="EVS Trend">
        <p style={{ padding: '10px', color: '#64748b', fontSize: '12px' }}>Loading history…</p>
      </Section>
    )
  }
  if (isError || !data?.history?.length) return null

  const history = data.history
  const BAR_W = 44
  const GAP = 10
  const CHART_H = 64
  const svgWidth = history.length * (BAR_W + GAP) - GAP
  const maxEvs = 100

  const flagColor = (flag: string) =>
    flag === 'high' ? '#ef4444' : flag === 'watch' ? '#f59e0b' : '#22c55e'

  const shortDate = (d: string) => {
    try { return new Date(d).toLocaleDateString('en-GB', { month: 'short', year: '2-digit' }) }
    catch { return d }
  }

  return (
    <Section title="EVS Trend">
      <div style={{ padding: '12px 10px 8px' }}>
        <svg width={svgWidth} height={CHART_H + 32} style={{ display: 'block', overflow: 'visible', width: '100%' }}>
          {history.map((pt: EVSHistoryPoint, i: number) => {
            const barH = Math.max(4, Math.round((pt.evs / maxEvs) * CHART_H))
            const x = i * (BAR_W + GAP)
            const color = flagColor(pt.flag)
            return (
              <g key={pt.observation_date}>
                {/* Bar */}
                <rect
                  x={x}
                  y={CHART_H - barH}
                  width={BAR_W}
                  height={barH}
                  fill={color}
                  fillOpacity={0.75}
                  rx={3}
                />
                {/* EVS label inside/above bar */}
                <text
                  x={x + BAR_W / 2}
                  y={CHART_H - barH - 4}
                  textAnchor="middle"
                  fontSize={10}
                  fill={color}
                  fontWeight={700}
                >
                  {pt.evs.toFixed(0)}
                </text>
                {/* Date label */}
                <text
                  x={x + BAR_W / 2}
                  y={CHART_H + 14}
                  textAnchor="middle"
                  fontSize={9}
                  fill="#475569"
                >
                  {shortDate(pt.observation_date)}
                </text>
                {/* Flag label */}
                <text
                  x={x + BAR_W / 2}
                  y={CHART_H + 26}
                  textAnchor="middle"
                  fontSize={8}
                  fill={color}
                  fontWeight={600}
                >
                  {pt.flag.toUpperCase()}
                </text>
              </g>
            )
          })}
          {/* Trend line */}
          {history.length > 1 && (
            <polyline
              points={history.map((pt: EVSHistoryPoint, i: number) => {
                const x = i * (BAR_W + GAP) + BAR_W / 2
                const y = CHART_H - Math.max(4, Math.round((pt.evs / maxEvs) * CHART_H))
                return `${x},${y}`
              }).join(' ')}
              fill="none"
              stroke="#60a5fa"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              opacity={0.6}
            />
          )}
        </svg>
        <p style={{ fontSize: '10px', color: '#334155', marginTop: '4px' }}>
          Synthetic observation history — demonstrates continuous monitoring capability.
        </p>
      </div>
    </Section>
  )
}

// ── E-1: Granite Explain Widget ───────────────────────────────────────────────

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  cached?: boolean
}

const SUGGESTED_QUESTIONS = [
  'Why is this facility flagged?',
  'What does the uncertainty interval mean?',
  'How is the EVS score calculated?',
  'What actions should be taken for a HIGH flag?',
]

function GraniteExplainWidget({ facilityId, facilityName }: { facilityId: string; facilityName: string }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendQuestion = async (question: string) => {
    if (!question.trim() || loading) return
    const q = question.trim()
    setInput('')
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const res = await explainFacilityEvs(facilityId, q)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.answer, cached: res.cached },
      ])
    } catch {
      setError('Unable to get an explanation. Check that the ML service is running.')
    } finally {
      setLoading(false)
    }
  }

  const formatAnswer = (text: string) => {
    // Convert **bold** markdown to styled spans and preserve newlines
    const parts = text.split(/(\*\*[^*]+\*\*)/)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>
      }
      return <span key={i}>{part}</span>
    })
  }

  return (
    <Section title="Ask Granite AI">
      {!open ? (
        <div style={{ padding: '10px' }}>
          <button
            type="button"
            onClick={() => setOpen(true)}
            style={{
              width: '100%',
              background: 'linear-gradient(135deg, #1e3a5f 0%, #0f1f3d 100%)',
              border: '1px solid #2563eb',
              borderRadius: '8px',
              padding: '10px 12px',
              color: '#93c5fd',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span style={{ fontSize: '16px' }}>🤖</span>
            <span>Ask IBM Granite to explain this EVS score</span>
          </button>
          <p style={{ fontSize: '10px', color: '#334155', marginTop: '6px' }}>
            Powered by IBM Granite · {facilityName}
          </p>
        </div>
      ) : (
        <div style={{ padding: '10px' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', color: '#60a5fa', fontWeight: 600 }}>
              🤖 IBM Granite — {facilityName}
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', fontSize: '14px' }}
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div style={{
            background: '#0a0c12',
            border: '1px solid #1e293b',
            borderRadius: '6px',
            padding: '8px',
            minHeight: '80px',
            maxHeight: '240px',
            overflowY: 'auto',
            marginBottom: '8px',
            fontSize: '12px',
            lineHeight: 1.55,
          }}>
            {messages.length === 0 && (
              <p style={{ color: '#334155', fontSize: '11px', margin: 0 }}>
                Ask a question about this facility's EVS score below.
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} style={{
                marginBottom: '8px',
                padding: '6px 8px',
                borderRadius: '5px',
                background: msg.role === 'user' ? '#1e293b' : '#0f1f3d',
                borderLeft: `2px solid ${msg.role === 'user' ? '#475569' : '#2563eb'}`,
              }}>
                <div style={{ fontSize: '10px', color: msg.role === 'user' ? '#64748b' : '#60a5fa', marginBottom: '3px', fontWeight: 600 }}>
                  {msg.role === 'user' ? 'You' : `IBM Granite${msg.cached ? ' (cached)' : ' (live)'}`}
                </div>
                <div style={{ color: msg.role === 'user' ? '#94a3b8' : '#cbd5e1', whiteSpace: 'pre-wrap' }}>
                  {msg.role === 'assistant' ? formatAnswer(msg.text) : msg.text}
                </div>
              </div>
            ))}
            {loading && (
              <div style={{ padding: '6px 8px', color: '#3b82f6', fontSize: '11px' }}>
                Granite is thinking…
              </div>
            )}
            {error && (
              <div style={{ padding: '6px 8px', color: '#f87171', fontSize: '11px' }}>
                {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Suggested questions */}
          {messages.length === 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '8px' }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => sendQuestion(q)}
                  disabled={loading}
                  style={{
                    background: '#1e293b',
                    border: '1px solid #2d3748',
                    borderRadius: '12px',
                    padding: '3px 8px',
                    color: '#93c5fd',
                    fontSize: '10px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    opacity: loading ? 0.5 : 1,
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div style={{ display: 'flex', gap: '6px' }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendQuestion(input)}
              placeholder="Ask a question…"
              disabled={loading}
              style={{
                flex: 1,
                background: '#0f1117',
                border: '1px solid #2d3148',
                borderRadius: '6px',
                color: '#e2e8f0',
                padding: '7px 9px',
                fontSize: '12px',
                outline: 'none',
              }}
            />
            <button
              type="button"
              onClick={() => sendQuestion(input)}
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? '#1e293b' : '#2563eb',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                color: '#eff6ff',
                padding: '7px 12px',
                cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                fontSize: '12px',
                fontWeight: 600,
                opacity: loading || !input.trim() ? 0.5 : 1,
              }}
            >
              Ask
            </button>
          </div>
          <p style={{ fontSize: '10px', color: '#334155', marginTop: '5px' }}>
            IBM Granite via watsonx.ai · context: EVS data for {facilityName}
          </p>
        </div>
      )}
    </Section>
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

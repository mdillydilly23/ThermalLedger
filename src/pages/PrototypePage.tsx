import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchFacilities, fetchPrototypeStatus, startVerificationRun } from '../lib/api'
import { useTask } from '../hooks/useTask'
import type { DiscrepancyFlag } from '../types/evs'

export function PrototypePage() {
  const queryClient = useQueryClient()
  const [selectedFacility, setSelectedFacility] = useState('EPA-GHGRP-TX-001')
  const [startDate, setStartDate] = useState('2024-06-01')
  const [endDate, setEndDate] = useState('2024-06-30')
  const [reuseRaw, setReuseRaw] = useState(true)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [requestError, setRequestError] = useState<string | null>(null)

  const statusQuery = useQuery({
    queryKey: ['prototype-status'],
    queryFn: fetchPrototypeStatus,
    refetchInterval: taskId ? 3000 : 15000,
  })
  const { data: status, isLoading: statusLoading, isError: statusError, refetch: refetchStatus } = statusQuery
  const facilitiesQuery = useQuery({
    queryKey: ['facilities'],
    queryFn: fetchFacilities,
  })
  const task = useTask(taskId)

  useEffect(() => {
    if (task?.status === 'SUCCESS') {
      refetchStatus()
      queryClient.invalidateQueries({ queryKey: ['facilities'] })
      queryClient.invalidateQueries({ queryKey: ['facility'] })
      queryClient.invalidateQueries({ queryKey: ['plume'] })
    }
  }, [queryClient, refetchStatus, task?.status])

  const facilities = facilitiesQuery.data?.facilities ?? []

  const runVerification = async () => {
    setRequestError(null)
    try {
      const response = await startVerificationRun({
        facility_ids: selectedFacility === 'all' ? undefined : [selectedFacility],
        start_date: startDate,
        end_date: endDate,
        reuse_existing_raw_data: reuseRaw,
      })
      setTaskId(response.task_id)
    } catch (error: unknown) {
      setRequestError(error instanceof Error ? error.message : 'Unable to start verification run.')
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Prototype Status</h1>
          <p style={styles.subtitle}>Live Sentinel-5P / ERA5 / Granite readiness</p>
        </div>
        <ModeBadge label={status?.granite_mode ?? 'loading'} tone={status?.granite_mode === 'live' ? 'green' : 'amber'} />
      </div>

      <div style={styles.grid}>
        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>Run Verification</h2>
          <label style={styles.label}>
            Facility
            <select value={selectedFacility} onChange={(event) => setSelectedFacility(event.target.value)} style={styles.input}>
              <option value="all">All facilities</option>
              {facilities.map((facility) => (
                <option key={facility.facility_id} value={facility.facility_id}>
                  {facility.facility_name}
                </option>
              ))}
            </select>
          </label>
          <div style={styles.dateRow}>
            <label style={styles.label}>
              Start
              <input value={startDate} onChange={(event) => setStartDate(event.target.value)} type="date" style={styles.input} />
            </label>
            <label style={styles.label}>
              End
              <input value={endDate} onChange={(event) => setEndDate(event.target.value)} type="date" style={styles.input} />
            </label>
          </div>
          <label style={styles.checkboxRow}>
            <input checked={reuseRaw} onChange={(event) => setReuseRaw(event.target.checked)} type="checkbox" />
            Reuse downloaded raw data
          </label>
          <button type="button" onClick={runVerification} style={styles.primaryButton}>
            Start live verification
          </button>
          {requestError && <p style={styles.error}>{requestError}</p>}
          {taskId && <TaskRunStatus taskId={taskId} task={task} />}
        </section>

        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>Readiness</h2>
          {statusLoading && <p style={styles.muted}>Loading status...</p>}
          {statusError && <p style={styles.error}>Unable to load prototype status.</p>}
          {status && (
            <>
              <div style={styles.badgeGrid}>
                <StatusBadge label="Backend" ok={status.service_health.backend} />
                <StatusBadge label="ML" ok={status.service_health.ml} />
                <StatusBadge label="Copernicus" ok={status.credentials.copernicus} />
                <StatusBadge label="CDS" ok={status.credentials.cds} />
                <StatusBadge label="watsonx" ok={status.credentials.watsonx} />
                <ModeBadge label={status.audit_mode.replace(/_/g, ' ')} tone="blue" />
              </div>
              <div style={styles.metrics}>
                <Metric label="Sentinel files" value={status.data.sentinel_raw_count} />
                <Metric label="ERA5 files" value={status.data.era5_raw_count} />
                <Metric label="Live plumes" value={status.data.processed_plume_count} />
                <Metric label="Audit anchors" value={status.data.audit_anchor_count} />
              </div>
              {(status.missing_setup ?? []).length > 0 && (
                <div style={styles.warningBox}>
                  {(status.missing_setup ?? []).map((item) => (
                    <div key={item}>{item}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>

      {status?.latest_run && (
        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>Latest Run</h2>
          <div style={styles.latestRow}>
            <Metric label="Status" value={status.latest_run.status} />
            <Metric label="Facilities" value={status.latest_run.facility_count} />
            <Metric label="Window" value={`${status.latest_run.observation_start} to ${status.latest_run.observation_end}`} />
            <Metric label="Source" value={status.latest_run.source} />
          </div>
          {status.latest_run.error && <p style={styles.error}>{status.latest_run.error}</p>}
        </section>
      )}
    </div>
  )
}

function TaskRunStatus({
  taskId,
  task,
}: {
  taskId: string
  task: ReturnType<typeof useTask>
}) {
  const result = task?.result as { scores?: Array<{ facility_id: string; facility_name: string; evs: number; flag: DiscrepancyFlag }> } | null

  if (!task) {
    return <p style={styles.muted}>Queued task {taskId}</p>
  }
  if (task.status === 'FAILURE') {
    return <p style={styles.error}>{task.error ?? 'Verification run failed.'}</p>
  }
  if (task.status !== 'SUCCESS') {
    return <p style={styles.muted}>{task.progress_stage ?? 'Processing live verification...'}</p>
  }

  return (
    <div style={styles.resultBox}>
      <div style={styles.success}>Verification run complete.</div>
      {(result?.scores ?? []).slice(0, 6).map((score) => (
        <div key={score.facility_id} style={styles.scoreRow}>
          <span>{score.facility_name}</span>
          <span>{score.evs.toFixed(1)} / {score.flag.toUpperCase()}</span>
        </div>
      ))}
    </div>
  )
}

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return <ModeBadge label={`${label}: ${ok ? 'ready' : 'missing'}`} tone={ok ? 'green' : 'red'} />
}

function ModeBadge({ label, tone }: { label: string; tone: 'green' | 'amber' | 'red' | 'blue' }) {
  const colors = {
    green: { bg: '#052e16', text: '#86efac', border: '#166534' },
    amber: { bg: '#451a03', text: '#fcd34d', border: '#92400e' },
    red: { bg: '#450a0a', text: '#fca5a5', border: '#991b1b' },
    blue: { bg: '#0f172a', text: '#93c5fd', border: '#1d4ed8' },
  }[tone]
  return (
    <span style={{
      ...styles.badge,
      background: colors.bg,
      color: colors.text,
      borderColor: colors.border,
    }}>
      {label}
    </span>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={styles.metricValue}>{value}</span>
    </div>
  )
}

const styles: Record<string, CSSProperties> = {
  page: {
    height: '100%',
    overflow: 'auto',
    padding: '28px',
    background: '#0f1117',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    gap: '16px',
  },
  title: { fontSize: '22px', margin: 0, color: '#e2e8f0' },
  subtitle: { margin: '6px 0 0', color: '#64748b', fontSize: '13px' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))',
    gap: '16px',
  },
  panel: {
    background: '#1a1d27',
    border: '1px solid #2d3148',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '16px',
  },
  panelTitle: { fontSize: '13px', textTransform: 'uppercase', color: '#94a3b8', letterSpacing: '0.04em', margin: '0 0 14px' },
  label: { display: 'flex', flexDirection: 'column', gap: '6px', color: '#64748b', fontSize: '12px', marginBottom: '12px' },
  input: {
    width: '100%',
    boxSizing: 'border-box',
    background: '#0f1117',
    border: '1px solid #2d3148',
    borderRadius: '6px',
    color: '#e2e8f0',
    padding: '8px',
    fontSize: '13px',
  },
  dateRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' },
  checkboxRow: { display: 'flex', alignItems: 'center', gap: '8px', color: '#94a3b8', fontSize: '13px', margin: '8px 0 14px' },
  primaryButton: {
    width: '100%',
    background: '#2563eb',
    color: '#eff6ff',
    border: '1px solid #3b82f6',
    borderRadius: '6px',
    padding: '9px 12px',
    cursor: 'pointer',
    fontWeight: 700,
  },
  muted: { color: '#64748b', fontSize: '13px' },
  error: { color: '#f87171', fontSize: '13px' },
  success: { color: '#4ade80', fontSize: '13px', marginBottom: '8px' },
  badgeGrid: { display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' },
  badge: { display: 'inline-flex', border: '1px solid', borderRadius: '999px', padding: '4px 8px', fontSize: '11px', textTransform: 'capitalize' },
  metrics: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' },
  metric: { background: '#0f1117', borderRadius: '6px', padding: '10px', border: '1px solid #2d3148' },
  metricLabel: { display: 'block', color: '#475569', fontSize: '11px', marginBottom: '4px' },
  metricValue: { color: '#e2e8f0', fontSize: '13px', wordBreak: 'break-word' },
  warningBox: { marginTop: '14px', padding: '10px', background: '#451a03', color: '#fcd34d', borderRadius: '6px', fontSize: '12px', lineHeight: 1.6 },
  resultBox: { marginTop: '12px', background: '#0f1117', border: '1px solid #2d3148', borderRadius: '6px', padding: '10px' },
  scoreRow: { display: 'flex', justifyContent: 'space-between', gap: '10px', padding: '5px 0', color: '#94a3b8', fontSize: '12px' },
  latestRow: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px' },
}

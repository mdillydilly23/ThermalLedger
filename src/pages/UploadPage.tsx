/**
 * UploadPage — ESG PDF upload flow with live task progress.
 * ADR-001: POST /esg/upload returns task_id, then polls GET /tasks/{id}.
 * ADR-006: In demo mode (GRANITE_MODE=cached) task completes instantly from cache.
 * H-4: upload state persisted to sessionStorage so tab-switching does not lose results.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ESGDropzone } from '../components/upload/ESGDropzone'
import { TaskProgress } from '../components/upload/TaskProgress'
import { fetchPrototypeStatus } from '../lib/api'

const SESSION_KEY = 'thermalledger_upload_state'

interface UploadState {
  taskId: string
  filename: string
}

function readSession(): UploadState | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as UploadState) : null
  } catch {
    return null
  }
}

function writeSession(state: UploadState | null) {
  try {
    if (state) {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(state))
    } else {
      sessionStorage.removeItem(SESSION_KEY)
    }
  } catch {
    // sessionStorage may be unavailable in some environments — silently ignore
  }
}

interface Props {
  /** Callback passed down into ParseResult so clicking a matched facility navigates to the map. */
  onNavigateToFacility?: (facilityId: string) => void
}

export function UploadPage({ onNavigateToFacility }: Props) {
  const [upload, setUpload] = useState<UploadState | null>(() => readSession())
  const { data: status } = useQuery({
    queryKey: ['prototype-status'],
    queryFn: fetchPrototypeStatus,
  })

  const handleUploadStart = (taskId: string, filename: string) => {
    const state: UploadState = { taskId, filename }
    writeSession(state)
    setUpload(state)
  }

  const handleReset = () => {
    writeSession(null)
    setUpload(null)
  }

  return (
    <div style={{
      maxWidth: '640px',
      margin: '0 auto',
      padding: '40px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '28px',
    }}>
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '6px' }}>
          ESG Report Upload
        </h1>
        <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.6 }}>
          Upload a corporate ESG PDF. IBM Granite will extract Scope 1 CH₄ emission
          claims which are then cross-referenced against satellite observations.
        </p>
        {status && (
          <div style={{
            display: 'inline-flex',
            marginTop: '10px',
            border: '1px solid #2d3148',
            borderRadius: '999px',
            padding: '4px 8px',
            color: status.granite_mode === 'live' ? '#86efac' : '#fcd34d',
            background: status.granite_mode === 'live' ? '#052e16' : '#451a03',
            fontSize: '11px',
            textTransform: 'capitalize',
          }}>
            Granite mode: {status.granite_mode}
          </div>
        )}
      </div>

      {/* Only show the dropzone when there is no active/completed upload */}
      {!upload && <ESGDropzone onUploadStart={handleUploadStart} />}

      {upload && (
        <div style={{
          background: '#1a1d27',
          border: '1px solid #2d3148',
          borderRadius: '10px',
          padding: '16px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ fontSize: '12px', color: '#475569' }}>
              Processing: <span style={{ color: '#94a3b8' }}>{upload.filename}</span>
            </div>
            <button
              type="button"
              onClick={handleReset}
              style={{
                background: 'none',
                border: '1px solid #2d3148',
                borderRadius: '5px',
                color: '#64748b',
                cursor: 'pointer',
                fontSize: '11px',
                padding: '3px 8px',
              }}
            >
              Upload another PDF
            </button>
          </div>
          <TaskProgress
            taskId={upload.taskId}
            label="ESG parse"
            onNavigateToFacility={onNavigateToFacility}
          />
        </div>
      )}

      {!upload && (
        <div style={{
          background: '#1a1d27',
          border: '1px solid #2d3148',
          borderRadius: '10px',
          padding: '16px',
          fontSize: '12px',
          color: '#475569',
          lineHeight: 1.7,
        }}>
          <div style={{ fontWeight: 600, color: '#64748b', marginBottom: '6px' }}>
            Demo mode (GRANITE_MODE=cached)
          </div>
          Any PDF will be processed instantly using pre-generated Granite outputs.
          The parsed emission claims will be displayed here and cross-matched with
          satellite EVS scores on the dashboard.
        </div>
      )}
    </div>
  )
}

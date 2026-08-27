/**
 * UploadPage — ESG PDF upload flow with live task progress.
 * ADR-001: POST /esg/upload returns task_id, then polls GET /tasks/{id}.
 * ADR-006: In demo mode (GRANITE_MODE=cached) task completes instantly from cache.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ESGDropzone } from '../components/upload/ESGDropzone'
import { TaskProgress } from '../components/upload/TaskProgress'
import { fetchPrototypeStatus } from '../lib/api'

interface UploadState {
  taskId: string
  filename: string
}

export function UploadPage() {
  const [upload, setUpload] = useState<UploadState | null>(null)
  const { data: status } = useQuery({
    queryKey: ['prototype-status'],
    queryFn: fetchPrototypeStatus,
  })

  const handleUploadStart = (taskId: string, filename: string) => {
    setUpload({ taskId, filename })
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

      <ESGDropzone onUploadStart={handleUploadStart} />

      {upload && (
        <div style={{
          background: '#1a1d27',
          border: '1px solid #2d3148',
          borderRadius: '10px',
          padding: '16px',
        }}>
          <div style={{ fontSize: '12px', color: '#475569', marginBottom: '12px' }}>
            Processing: <span style={{ color: '#94a3b8' }}>{upload.filename}</span>
          </div>
          <TaskProgress taskId={upload.taskId} label="ESG parse" />
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

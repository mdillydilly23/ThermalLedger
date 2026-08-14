/**
 * ESGDropzone — drag-and-drop PDF upload widget.
 * Calls POST /esg/upload, returns task_id for polling.
 */

import { useState, useRef, DragEvent } from 'react'
import { uploadESGPdf } from '../../lib/api'

interface Props {
  onUploadStart: (taskId: string, filename: string) => void
}

export function ESGDropzone({ onUploadStart }: Props) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are accepted.')
      return
    }
    setError(null)
    setUploading(true)
    try {
      const res = await uploadESGPdf(file)
      onUploadStart(res.task_id, res.filename)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div>
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          border: `2px dashed ${dragging ? '#60a5fa' : '#2d3148'}`,
          borderRadius: '12px',
          padding: '48px 24px',
          textAlign: 'center',
          cursor: uploading ? 'wait' : 'pointer',
          background: dragging ? 'rgba(96,165,250,0.05)' : '#0f1117',
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        <div style={{ fontSize: '32px', marginBottom: '12px' }}>📄</div>
        <div style={{ fontSize: '14px', color: '#94a3b8' }}>
          {uploading
            ? 'Uploading…'
            : 'Drop a corporate ESG PDF here, or click to browse'}
        </div>
        <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px' }}>
          Accepts PDF only — Granite will extract CH₄ emission claims
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        style={{ display: 'none' }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
      />

      {error && (
        <p style={{ color: '#f87171', fontSize: '13px', marginTop: '8px' }}>{error}</p>
      )}
    </div>
  )
}

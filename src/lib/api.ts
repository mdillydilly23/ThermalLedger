/**
 * API client — all backend calls go through here.
 * ADR-001: uses fetch with async/await.
 * ADR-004: return types match Pydantic models from backend.
 */

import type {
  EVSScore,
  FacilitySummary,
  PrototypeStatus,
  TaskStatus,
  VerificationRunRequest,
  VerificationRunResponse,
} from '../types/evs'

const BASE = '/api'  // proxied to backend:8000 by Vite (vite.config.ts)

// Demo API key — matches DEMO_API_KEY in .env / backend/app/api/deps.py.
// Falls back to the well-known demo value so local dev works without extra setup.
const API_KEY = (import.meta.env.VITE_DEMO_API_KEY as string | undefined) ?? 'thermalledger-demo'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': API_KEY,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

// ── Facilities ────────────────────────────────────────────────

export const fetchFacilities = (): Promise<{ facilities: FacilitySummary[]; total: number }> =>
  get('/facilities')

export const fetchFacilityDetail = (id: string): Promise<EVSScore> =>
  get(`/facilities/${id}`)

// ── Plume ─────────────────────────────────────────────────────

export interface PlumePointFeature {
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: { weight: number; source: string }
}

export interface PlumeGeoJSONResponse {
  facility_id: string
  observation_date: string
  geojson: { type: 'FeatureCollection'; features: PlumePointFeature[] }
  source: string
  cached: boolean
}

export const fetchPlumeGeoJSON = (facilityId: string, date: string): Promise<PlumeGeoJSONResponse> =>
  get(`/plume/${facilityId}/geojson?observation_date=${date}`)

// ── ESG upload ────────────────────────────────────────────────

export async function uploadESGPdf(file: File): Promise<{ task_id: string; filename: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/esg/upload`, {
    method: 'POST',
    headers: { 'X-Api-Key': API_KEY },
    body: form,
  })
  if (!res.ok) throw new Error(`ESG upload failed: ${res.status}`)
  return res.json()
}

// ── Reports ───────────────────────────────────────────────────

export const generateReport = (
  facilityId: string,
  start: string,
  end: string
): Promise<{ task_id: string }> =>
  post('/reports/generate', {
    facility_id: facilityId,
    observation_start: start,
    observation_end: end,
  })

// ── Granite explain (E-1) ─────────────────────────────────────

export interface ExplainResponse {
  facility_id: string
  question: string
  answer: string
  cached: boolean
}

export const explainFacilityEvs = (
  facilityId: string,
  question: string,
): Promise<ExplainResponse> =>
  post(`/facilities/${facilityId}/explain`, { question })

// ── EVS history (E-2) ─────────────────────────────────────────

export interface EVSHistoryPoint {
  observation_date: string
  evs: number
  flag: string
  satellite_ch4_estimate: number
  reported_ch4: number | null
}

export interface EVSHistoryResponse {
  facility_id: string
  history: EVSHistoryPoint[]
}

export const fetchFacilityHistory = (facilityId: string): Promise<EVSHistoryResponse> =>
  get(`/facilities/${facilityId}/history`)

// ── Task polling (ADR-001: async background task pattern) ─────

export const pollTask = (taskId: string): Promise<TaskStatus> =>
  get(`/tasks/${taskId}`)

// ── Live prototype controls ───────────────────────────────────

export const fetchPrototypeStatus = (): Promise<PrototypeStatus> =>
  get('/prototype/status')

export const startVerificationRun = (
  request: VerificationRunRequest,
): Promise<VerificationRunResponse> =>
  post('/verification/runs', request)

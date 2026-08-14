/**
 * ADR-003: EVS TypeScript interface — mirrors shared/evs_schema.py exactly.
 *
 * This file is the hand-written bootstrap. Once the backend is running,
 * regenerate from the OpenAPI spec:
 *   pnpm run generate:types
 * which overwrites src/types/api.ts. This file re-exports from there.
 *
 * ADR-004: All types ultimately derived from Pydantic models via OpenAPI.
 */

export type DiscrepancyFlag = 'clear' | 'watch' | 'high'

export interface EVSScore {
  // Identity
  facility_id: string
  facility_name: string
  latitude: number
  longitude: number

  // Observation window
  observation_start: string   // ISO date
  observation_end: string     // ISO date
  days_with_valid_retrievals: number
  coverage_pct: number        // 0–100

  // Satellite estimate
  satellite_ch4_estimate: number
  satellite_uncertainty_low: number
  satellite_uncertainty_high: number

  // Corporate self-reported
  reported_ch4: number | null
  reported_source: string | null
  reported_year: number | null

  // Scoring
  delta_pct: number | null
  sigma_deviation: number | null
  evs: number                 // 0–100
  flag: DiscrepancyFlag

  // Audit
  blockchain_tx_id: string | null
  report_id: string | null
}

export interface FacilitySummary {
  facility_id: string
  facility_name: string
  latitude: number
  longitude: number
  sector: string
  latest_evs: number | null
  latest_flag: DiscrepancyFlag | null
}

export interface TaskStatus {
  task_id: string
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE'
  progress_stage: string | null
  result: unknown | null
  error: string | null
}

/** EVS score → map marker color (ADR-005: Deck.gl ScatterplotLayer color) */
export function evsFlagToRGB(flag: DiscrepancyFlag): [number, number, number] {
  switch (flag) {
    case 'high':  return [220, 38, 38]    // red-600
    case 'watch': return [217, 119, 6]    // amber-600
    case 'clear': return [22, 163, 74]    // green-600
  }
}

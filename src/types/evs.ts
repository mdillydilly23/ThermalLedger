/**
 * Frontend API types.
 *
 * ADR-004: generated OpenAPI types live in src/types/api.ts.  This file keeps
 * ergonomic aliases and UI-only helper types in one place.
 */

import type { components } from './api'

type Schema<Name extends keyof components['schemas']> = components['schemas'][Name]

export type DiscrepancyFlag = Schema<'DiscrepancyFlag'>
export type EVSScore = Schema<'EVSScore'>
export type FacilitySummary = Schema<'FacilitySummary'>
export type PrototypeStatus = Schema<'PrototypeStatus'>
export type VerificationRunResponse = Schema<'VerificationRunResponse'>

export type TaskStatus = Schema<'TaskStatus'> & {
  status: 'PENDING' | 'STARTED' | 'PROGRESS' | 'SUCCESS' | 'FAILURE'
}

export type VerificationRunRequest = Omit<Schema<'VerificationRunRequest'>, 'bbox'> & {
  bbox?: [number, number, number, number]
}

export interface ESGClaimMatch {
  facility_id: string
  facility_name: string
  claim_year: number | null
  reported_ch4: number | null
  latest_evs: number | null
  latest_flag: DiscrepancyFlag | null
  match_reason: string | null
}

/** EVS score flag to map marker color. */
export function evsFlagToRGB(flag: DiscrepancyFlag): [number, number, number] {
  switch (flag) {
    case 'high':  return [220, 38, 38]
    case 'watch': return [217, 119, 6]
    case 'clear': return [22, 163, 74]
  }
}

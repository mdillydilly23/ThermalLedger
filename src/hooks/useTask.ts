/**
 * useTask — polls GET /tasks/{taskId} until SUCCESS or FAILURE.
 * ADR-001: drives the step-by-step pipeline progress indicator in the demo UI.
 */

import { useEffect, useState } from 'react'
import { pollTask } from '../lib/api'
import type { TaskStatus } from '../types/evs'

const POLL_INTERVAL_MS = 1500
const MAX_BACKOFF_MS = 30_000

export function useTask(taskId: string | null): TaskStatus | null {
  const [status, setStatus] = useState<TaskStatus | null>(null)

  useEffect(() => {
    if (!taskId) return
    let active = true
    let errorCount = 0

    const poll = async () => {
      try {
        const result = await pollTask(taskId)
        if (!active) return
        errorCount = 0
        setStatus(result)
        if (result.status !== 'SUCCESS' && result.status !== 'FAILURE') {
          setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch {
        // exponential backoff with a cap on repeated errors
        if (active) {
          errorCount++
          const backoff = Math.min(POLL_INTERVAL_MS * 2 ** errorCount, MAX_BACKOFF_MS)
          setTimeout(poll, backoff)
        }
      }
    }

    poll()
    return () => { active = false }
  }, [taskId])

  return status
}

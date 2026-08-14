/**
 * useTask — polls GET /tasks/{taskId} until SUCCESS or FAILURE.
 * ADR-001: drives the step-by-step pipeline progress indicator in the demo UI.
 */

import { useEffect, useState } from 'react'
import { pollTask } from '../lib/api'
import type { TaskStatus } from '../types/evs'

const POLL_INTERVAL_MS = 1500

export function useTask(taskId: string | null): TaskStatus | null {
  const [status, setStatus] = useState<TaskStatus | null>(null)

  useEffect(() => {
    if (!taskId) return
    let active = true

    const poll = async () => {
      try {
        const result = await pollTask(taskId)
        if (!active) return
        setStatus(result)
        if (result.status !== 'SUCCESS' && result.status !== 'FAILURE') {
          setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch {
        // retry on transient errors
        if (active) setTimeout(poll, POLL_INTERVAL_MS * 2)
      }
    }

    poll()
    return () => { active = false }
  }, [taskId])

  return status
}

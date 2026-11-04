import { useState, useCallback } from 'react'
import { runTraining, getComparison } from '../services/api'

/**
 * Custom hook for managing training run lifecycle.
 * Handles training execution, polling, and comparison retrieval.
 * 
 * @returns {Object} Run state and control functions
 */
export function useRun() {
  const [running, setRunning] = useState(false)
  const [runId, setRunId] = useState(null)
  const [trainingResult, setTrainingResult] = useState(null)
  const [comparisonResult, setComparisonResult] = useState(null)
  const [error, setError] = useState(null)

  const startTraining = useCallback(async (config) => {
    setRunning(true)
    setError(null)
    try {
      const result = await runTraining(config)
      setRunId(result.run_id)
      setTrainingResult(result)
      return result
    } catch (err) {
      setError(err.message || 'Training failed')
      throw err
    } finally {
      setRunning(false)
    }
  }, [])

  const fetchComparison = useCallback(async (id) => {
    const targetId = id || runId
    if (!targetId) {
      throw new Error('No run ID available')
    }

    try {
      const result = await getComparison(targetId)
      setComparisonResult(result)
      return result
    } catch (err) {
      setError(err.message || 'Failed to fetch comparison')
      throw err
    }
  }, [runId])

  const reset = useCallback(() => {
    setRunning(false)
    setRunId(null)
    setTrainingResult(null)
    setComparisonResult(null)
    setError(null)
  }, [])

  return {
    running,
    runId,
    trainingResult,
    comparisonResult,
    error,
    startTraining,
    fetchComparison,
    reset
  }
}

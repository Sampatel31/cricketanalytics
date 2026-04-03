import { useState } from 'react'
import { dnaAPI } from '../services/api'
import type { FranchiseDNA, DNASliderRequest, DNAExemplarRequest, DNAHistoricalRequest } from '../types/api'

export function useDNA(
  mode: 'slider' | 'exemplar' | 'historical',
  params: DNASliderRequest | DNAExemplarRequest | DNAHistoricalRequest
) {
  const [dna, setDNA] = useState<FranchiseDNA | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const build = async () => {
    setLoading(true)
    setError(null)
    try {
      let res
      if (mode === 'slider') {
        res = await dnaAPI.slider(params as DNASliderRequest)
      } else if (mode === 'exemplar') {
        res = await dnaAPI.exemplar(params as DNAExemplarRequest)
      } else {
        res = await dnaAPI.historical(params as DNAHistoricalRequest)
      }
      setDNA(res.data as FranchiseDNA)
      return res.data as FranchiseDNA
    } catch (err) {
      setError(err instanceof Error ? err.message : 'DNA build failed')
      return null
    } finally {
      setLoading(false)
    }
  }

  return { dna, build, loading, error }
}

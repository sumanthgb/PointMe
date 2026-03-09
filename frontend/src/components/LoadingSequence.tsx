import { useEffect, useState } from 'react'
import { CheckCircle, AlertCircle, Loader, XCircle } from 'lucide-react'
import type { LoadingStep } from '../types'

const SOURCE_SEQUENCE: Array<{ id: string; label: string; preview: string; delay: number; duration: number }> = [
  { id: 'open_targets', label: 'Open Targets', preview: 'Fetching genetic associations & tractability…', delay: 0, duration: 900 },
  { id: 'clinicaltrials', label: 'ClinicalTrials.gov', preview: 'Querying trial history & failure reasons…', delay: 600, duration: 1100 },
  { id: 'pubmed', label: 'PubMed / Europe PMC', preview: 'Scanning literature corpus…', delay: 1000, duration: 1400 },
  { id: 'uniprot', label: 'UniProt', preview: 'Retrieving tissue expression & protein function…', delay: 1400, duration: 800 },
  { id: 'fda_drugs', label: 'Drugs@FDA', preview: 'Checking approved drugs & regulatory precedent…', delay: 1700, duration: 950 },
  { id: 'orange_book', label: 'FDA Orange Book', preview: 'Analyzing IP landscape & patent expiries…', delay: 2100, duration: 850 },
]

const ENGINE_STEPS = [
  { id: 'xref', label: 'Running cross-reference engine…', delay: 3200 },
  { id: 'score', label: 'Computing evidence scores…', delay: 3700 },
  { id: 'reg', label: 'Evaluating regulatory pathway…', delay: 4100 },
  { id: 'llm', label: 'Generating synthesis…', delay: 4500 },
]

interface Props {
  target: string
  disease: string
}

export function LoadingSequence({ target, disease }: Props) {
  const [steps, setSteps] = useState<LoadingStep[]>(
    SOURCE_SEQUENCE.map((s) => ({ id: s.id, label: s.label, status: 'pending', preview: s.preview }))
  )
  const [engineIdx, setEngineIdx] = useState(-1)

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []

    SOURCE_SEQUENCE.forEach((src, idx) => {
      // start running
      timers.push(
        setTimeout(() => {
          setSteps((prev) =>
            prev.map((s, i) => (i === idx ? { ...s, status: 'running' } : s))
          )
        }, src.delay)
      )
      // finish
      timers.push(
        setTimeout(() => {
          const ms = 280 + Math.floor(Math.random() * 700)
          setSteps((prev) =>
            prev.map((s, i) =>
              i === idx ? { ...s, status: idx === 5 ? 'partial' : 'success', time_ms: ms } : s
            )
          )
        }, src.delay + src.duration)
      )
    })

    ENGINE_STEPS.forEach((step, idx) => {
      timers.push(
        setTimeout(() => setEngineIdx(idx), step.delay)
      )
    })

    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <div className="w-full max-w-lg mx-auto fade-up space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <p className="label-mono">Evaluating</p>
        <h2 className="text-lg font-semibold text-ink">
          <span className="font-mono text-teal">{target}</span>
          <span className="text-ink-3 mx-2">×</span>
          <span className="text-ink-2">{disease}</span>
        </h2>
      </div>

      {/* Source steps */}
      <div className="card space-y-3">
        <p className="label-mono">Data sources</p>
        {steps.map((step) => (
          <div key={step.id} className="flex items-start gap-3">
            <StepIcon status={step.status} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className={`text-sm font-medium ${step.status === 'pending' ? 'text-ink-4' : 'text-ink'}`}>
                  {step.label}
                </span>
                {step.time_ms && (
                  <span className="font-mono text-xs text-ink-3">{step.time_ms}ms</span>
                )}
              </div>
              {step.status === 'running' && (
                <p className="text-xs text-ink-3 mt-0.5 truncate">{step.preview}</p>
              )}
              {step.status === 'partial' && (
                <p className="text-xs text-caution mt-0.5">Partial data — some fields unavailable</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Engine steps */}
      {engineIdx >= 0 && (
        <div className="card space-y-2">
          <p className="label-mono">Analysis pipeline</p>
          {ENGINE_STEPS.slice(0, engineIdx + 1).map((step, idx) => (
            <div key={step.id} className="flex items-center gap-3">
              {idx < engineIdx ? (
                <CheckCircle size={14} className="text-go flex-shrink-0" />
              ) : (
                <Loader size={14} className="text-teal flex-shrink-0 animate-spin" />
              )}
              <span className={`text-sm ${idx < engineIdx ? 'text-ink-3' : 'text-ink-2'}`}>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StepIcon({ status }: { status: LoadingStep['status'] }) {
  if (status === 'pending') return <div className="w-3.5 h-3.5 rounded-full border border-border mt-0.5 flex-shrink-0" />
  if (status === 'running') return <Loader size={14} className="text-teal animate-spin mt-0.5 flex-shrink-0" />
  if (status === 'success') return <CheckCircle size={14} className="text-go mt-0.5 flex-shrink-0" />
  if (status === 'partial') return <AlertCircle size={14} className="text-caution mt-0.5 flex-shrink-0" />
  return <XCircle size={14} className="text-nogo mt-0.5 flex-shrink-0" />
}

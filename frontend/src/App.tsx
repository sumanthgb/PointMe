import { useState, useCallback } from 'react'
import { ArrowLeft, Download, ExternalLink, Target, Github } from 'lucide-react'
import type { PointMeResponse, AppState } from './types'
import { SearchBar } from './components/SearchBar'
import { LoadingSequence } from './components/LoadingSequence'
import { VerdictHero } from './components/VerdictHero'
import { EvidenceTabs } from './components/EvidenceTabs'
import { RegulatoryTree } from './components/RegulatoryTree'
import { RiskFlags } from './components/RiskFlags'
import { LLMSynthesis } from './components/LLMSynthesis'
import { DataSourceBar } from './components/DataSourceBar'
import { IPPanel } from './components/IPPanel'

type ResultsTab = 'overview' | 'science' | 'regulatory' | 'ip' | 'flags'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

async function evaluateTarget(target: string, disease: string): Promise<PointMeResponse> {
  const res = await fetch(`${API_BASE}/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target, disease }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export default function App() {
  const [state, setState] = useState<AppState>('idle')
  const [data, setData] = useState<PointMeResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState<{ target: string; disease: string } | null>(null)
  const [activeTab, setActiveTab] = useState<ResultsTab>('overview')

  const handleSubmit = useCallback(async (target: string, disease: string) => {
    setQuery({ target, disease })
    setState('loading')
    setError(null)

    try {
      const result = await evaluateTarget(target, disease)
      setData(result)
      setState('results')
      setActiveTab('overview')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed')
      setState('error')
    }
  }, [])

  const handleReset = useCallback(() => {
    setState('idle')
    setData(null)
    setError(null)
    setQuery(null)
  }, [])

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {/* Nav */}
      <nav className="border-b border-border bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-teal flex items-center justify-center">
              <Target size={14} className="text-white" />
            </div>
            <span className="font-semibold text-sm text-ink tracking-tight">PointMe</span>
            <span className="hidden sm:block text-xs text-ink-4 font-mono ml-1 border-l border-border pl-2">
              Drug Target Validation
            </span>
          </div>
          <div className="flex items-center gap-3">
            {state === 'results' && (
              <button onClick={handleReset} className="btn-ghost flex items-center gap-1.5 text-xs py-1.5">
                <ArrowLeft size={12} /> New Search
              </button>
            )}
            <a
              href="https://github.com/sumanthgb/PointMe"
              target="_blank"
              rel="noopener noreferrer"
              className="text-ink-4 hover:text-ink-2 transition-colors"
            >
              <Github size={16} />
            </a>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-16">
        {/* IDLE */}
        {state === 'idle' && (
          <div className="min-h-[85vh] flex flex-col items-center justify-center py-16 space-y-10">
            <div className="text-center space-y-4 max-w-xl">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-2 border border-border text-xs text-ink-4 font-mono mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-go animate-pulse" />
                6 live databases · Real-time analysis
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-ink leading-tight tracking-tight">
                The checkpoint between
                <br />
                <span className="text-teal">discovery</span> and <span className="text-teal">development</span>
              </h1>
              <p className="text-ink-3 leading-relaxed text-sm sm:text-base">
                Cross-reference genetic evidence, clinical trial history, regulatory precedent, and safety signals
                in seconds — before committing to clinical development.
              </p>
              <div className="flex items-center justify-center gap-4 text-xs text-ink-4 font-mono flex-wrap">
                <span>Open Targets</span><span>·</span>
                <span>ClinicalTrials.gov</span><span>·</span>
                <span>PubMed</span><span>·</span>
                <span>UniProt</span><span>·</span>
                <span>Drugs@FDA</span><span>·</span>
                <span>FDA Orange Book</span>
              </div>
            </div>
            <SearchBar onSubmit={handleSubmit} />
            <ValueProps />
          </div>
        )}

        {/* LOADING */}
        {state === 'loading' && query && (
          <div className="min-h-[85vh] flex flex-col items-center justify-center py-16">
            <LoadingSequence target={query.target} disease={query.disease} />
          </div>
        )}

        {/* ERROR */}
        {state === 'error' && (
          <div className="min-h-[85vh] flex flex-col items-center justify-center py-16 space-y-4">
            <div className="card max-w-md w-full text-center space-y-3">
              <p className="text-nogo font-medium">Evaluation failed</p>
              <p className="text-sm text-ink-3">{error}</p>
              <p className="text-xs text-ink-4">
                Make sure the backend is running at localhost:8001.
              </p>
              <button onClick={handleReset} className="btn-primary mx-auto">
                Try Again
              </button>
            </div>
          </div>
        )}

        {/* RESULTS */}
        {state === 'results' && data && (
          <div className="py-8 space-y-6 fade-up">
            {/* Result header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-lg font-semibold text-ink">{data.target}</span>
                  <span className="text-ink-4">×</span>
                  <span className="text-ink-2">{data.disease}</span>
                </div>
                <p className="text-xs text-ink-4 mt-0.5 font-mono">
                  Evaluated across {Object.keys(data.data_sources).length} sources ·{' '}
                  {Object.values(data.data_sources).reduce((s, v) => s + v.query_time_ms, 0)}ms total
                </p>
              </div>
              <ExportButton data={data} />
            </div>

            {/* Verdict hero */}
            <VerdictHero data={data} />

            {/* Tab navigation */}
            <div className="border-b border-border overflow-x-auto">
              <div className="flex">
                {(
                  [
                    { id: 'overview', label: 'Overview' },
                    { id: 'science', label: 'Scientific Evidence' },
                    { id: 'regulatory', label: 'Regulatory Pathway' },
                    { id: 'ip', label: 'IP & Privacy' },
                    { id: 'flags', label: `Risk Flags${data.flags.length > 0 ? ` (${data.flags.length})` : ''}` },
                  ] as Array<{ id: ResultsTab; label: string }>
                ).map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`tab-btn ${activeTab === tab.id ? 'tab-btn-active' : ''} ${
                      tab.id === 'flags' && data.flags.some((f) => f.severity === 'critical') && activeTab !== tab.id
                        ? 'text-nogo/70'
                        : ''
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Tab content */}
            <div className="space-y-5">
              {activeTab === 'overview' && <OverviewTab data={data} onTabChange={setActiveTab} />}
              {activeTab === 'science' && <EvidenceTabs evidence={data.scientific_evidence} />}
              {activeTab === 'regulatory' && <RegulatoryTree assessment={data.regulatory_assessment} />}
              {activeTab === 'ip' && <IPPanel data={data} />}
              {activeTab === 'flags' && <RiskFlags flags={data.flags} />}
            </div>

            <DataSourceBar sources={data.data_sources} />
          </div>
        )}
      </main>
    </div>
  )
}

function OverviewTab({
  data,
  onTabChange,
}: {
  data: PointMeResponse
  onTabChange: (tab: ResultsTab) => void
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* Left: Science summary */}
      <div className="card space-y-4">
        <div className="flex items-center justify-between">
          <p className="label-mono">Scientific evidence summary</p>
          <button onClick={() => onTabChange('science')} className="text-xs text-teal hover:underline flex items-center gap-1">
            View all <ExternalLink size={9} />
          </button>
        </div>
        <MetricRow
          label="Genetic association score"
          value={data.scientific_evidence.genetic.score.toFixed(2)}
          numericVal={data.scientific_evidence.genetic.score}
          source={{ label: 'Open Targets', url: 'https://www.opentargets.org' }}
          color="#0D4F4F"
        />
        <MetricRow
          label="Literature relevance"
          value={data.scientific_evidence.literature.relevance_score.toFixed(2)}
          numericVal={data.scientific_evidence.literature.relevance_score}
          source={{ label: `${data.scientific_evidence.literature.total_papers.toLocaleString()} papers · PubMed`, url: 'https://pubmed.ncbi.nlm.nih.gov' }}
          color="#0D4F4F"
        />
        <MetricRow
          label="Trial success rate"
          value={`${(data.scientific_evidence.clinical_trials.success_rate * 100).toFixed(0)}%`}
          numericVal={data.scientific_evidence.clinical_trials.success_rate}
          source={{ label: `${data.scientific_evidence.clinical_trials.failed} failed · ClinicalTrials.gov`, url: 'https://clinicaltrials.gov' }}
          color={data.scientific_evidence.clinical_trials.success_rate > 0.6 ? '#2D936C' : data.scientific_evidence.clinical_trials.success_rate > 0.3 ? '#D4930D' : '#C1292E'}
          ci={data.scores.confidence ? {
            low: data.scores.confidence.success_rate_ci_low,
            high: data.scores.confidence.success_rate_ci_high,
            n: data.scores.confidence.n_trials_observed,
          } : undefined}
        />
        <MetricRow
          label="Tractability score"
          value={data.scientific_evidence.tractability.score.toFixed(2)}
          numericVal={data.scientific_evidence.tractability.score}
          source={{ label: `${data.scientific_evidence.tractability.molecule_type} · Open Targets`, url: 'https://www.opentargets.org' }}
          color="#B8953E"
        />
      </div>

      {/* Right: Regulatory + flags summary */}
      <div className="space-y-4">
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <p className="label-mono">Regulatory pathway summary</p>
            <button onClick={() => onTabChange('regulatory')} className="text-xs text-teal hover:underline flex items-center gap-1">
              Full analysis <ExternalLink size={9} />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="label-mono">Pathway</p>
              <p className="font-mono text-sm font-semibold text-ink mt-1">
                {data.regulatory_assessment.recommended_pathway ?? '—'}
              </p>
            </div>
            <div>
              <p className="label-mono">Timeline</p>
              <p className="font-mono text-sm text-ink mt-1">
                {data.regulatory_assessment.estimated_timeline_years ?? '—'}
              </p>
            </div>
            <div>
              <p className="label-mono">Est. cost</p>
              <p className="font-mono text-sm text-ink mt-1">
                {data.regulatory_assessment.estimated_cost_range ?? '—'}
              </p>
            </div>
            <div>
              <p className="label-mono">Designations</p>
              <p className="font-mono text-sm text-ink mt-1">
                {data.regulatory_assessment.special_designations.length > 0
                  ? `${data.regulatory_assessment.special_designations.length} available`
                  : 'None'}
              </p>
            </div>
          </div>
          {data.regulatory_assessment.special_designations.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.regulatory_assessment.special_designations.map((d) => (
                <span key={d} className="text-xs font-mono px-2 py-0.5 rounded-full bg-teal-light border border-teal-border text-teal">
                  {d.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
        </div>

        {data.flags.length > 0 && (
          <div className="card space-y-3">
            <div className="flex items-center justify-between">
              <p className="label-mono">Risk flags</p>
              <button onClick={() => onTabChange('flags')} className="text-xs text-teal hover:underline flex items-center gap-1">
                View all <ExternalLink size={9} />
              </button>
            </div>
            <div className="space-y-2">
              {data.flags.slice(0, 2).map((flag, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className={`text-xs font-mono font-bold uppercase px-1.5 py-0.5 rounded flex-shrink-0 ${
                    flag.severity === 'critical' ? 'text-nogo bg-nogo-light'
                    : flag.severity === 'high' ? 'text-caution bg-caution-light'
                    : 'text-ink-3 bg-surface-2'
                  }`}>
                    {flag.severity}
                  </span>
                  <p className="text-xs text-ink-3 leading-relaxed line-clamp-2">{flag.message}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* LLM Synthesis spans full width */}
      <div className="lg:col-span-2">
        <LLMSynthesis synthesis={data.llm_synthesis} target={data.target} disease={data.disease} />
      </div>
    </div>
  )
}

function MetricRow({
  label, value, numericVal, source, color, ci,
}: {
  label: string
  value: string
  numericVal: number
  source: { label: string; url: string }
  color: string
  ci?: { low: number; high: number; n: number }
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs text-ink-3">{label}</span>
          {ci && ci.n > 0 && (
            <span className="font-mono text-[10px] text-ink-4 ml-1.5">
              95% CI [{(ci.low * 100).toFixed(0)}–{(ci.high * 100).toFixed(0)}%] · N={ci.n}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold" style={{ color }}>{value}</span>
          <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-chip">
            {source.label} <ExternalLink size={9} />
          </a>
        </div>
      </div>
      <div className="h-1 bg-surface-3 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${Math.min(numericVal, 1) * 100}%`, background: color }} />
      </div>
    </div>
  )
}

function ExportButton({ data }: { data: PointMeResponse }) {
  function handleExport() {
    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `pointme-${data.target.replace(/\s+/g, '_')}-${data.disease.replace(/\s+/g, '_')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <button onClick={handleExport} className="btn-ghost flex items-center gap-1.5 text-xs py-1.5">
      <Download size={12} /> Export JSON
    </button>
  )
}

function ValueProps() {
  const props = [
    { icon: '🧬', title: 'Genetic evidence', desc: 'GWAS & rare-variant associations from Open Targets — the #1 predictor of clinical success' },
    { icon: '📋', title: 'Trial history', desc: 'Every phase, failure reason, and stopping criterion from ClinicalTrials.gov' },
    { icon: '⚡', title: 'Cross-reference engine', desc: 'Catches contradictions and corroborated risks that siloed review misses' },
    { icon: '🏛', title: 'Regulatory pathway', desc: 'Deterministic rules engine — every decision is logged and auditable' },
  ]
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full max-w-2xl">
      {props.map((p) => (
        <div key={p.title} className="card text-center space-y-1.5 py-4">
          <span className="text-2xl">{p.icon}</span>
          <p className="text-xs font-semibold text-ink-2">{p.title}</p>
          <p className="text-xs text-ink-4 leading-relaxed">{p.desc}</p>
        </div>
      ))}
    </div>
  )
}

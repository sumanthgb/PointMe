import { AlertTriangle, AlertOctagon, Info, Zap, ExternalLink } from 'lucide-react'
import type { CrossReferenceFlag } from '../types'

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertOctagon,
    color: '#C1292E',
    bg: 'rgba(193,41,46,0.07)',
    border: 'rgba(193,41,46,0.22)',
    badge: 'text-nogo bg-nogo-light border border-nogo-border',
    label: 'CRITICAL',
  },
  high: {
    icon: AlertTriangle,
    color: '#D4930D',
    bg: 'rgba(212,147,13,0.07)',
    border: 'rgba(212,147,13,0.22)',
    badge: 'text-caution bg-caution-light border border-caution-border',
    label: 'HIGH',
  },
  medium: {
    icon: AlertTriangle,
    color: '#6A6A6E',
    bg: '',
    border: '',
    badge: 'text-ink-3 bg-surface-2 border border-border',
    label: 'MEDIUM',
  },
  low: {
    icon: Info,
    color: '#9A9A9E',
    bg: '',
    border: '',
    badge: 'text-ink-4 bg-surface-3 border border-border',
    label: 'LOW',
  },
}

const TYPE_LABELS: Record<string, string> = {
  contradiction: 'Genetic–Clinical Contradiction',
  safety_flag: 'Safety Signal',
  corroborated_risk: 'Corroborated Risk',
  ip_risk: 'IP Risk',
  data_gap: 'Data Gap',
}

interface Props {
  flags: CrossReferenceFlag[]
}

export function RiskFlags({ flags }: Props) {
  if (!flags.length) {
    return (
      <div className="card flex items-center gap-3 text-ink-3">
        <Info size={16} />
        <span className="text-sm">No risk flags detected.</span>
      </div>
    )
  }

  const sorted = [...flags].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 }
    return order[a.severity] - order[b.severity]
  })

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Zap size={14} className="text-ink-3" />
        <p className="label-mono">Cross-reference engine findings</p>
        <span className="text-xs text-ink-3 font-mono ml-auto">{flags.length} flag{flags.length !== 1 ? 's' : ''}</span>
      </div>

      {sorted.map((flag, idx) => {
        const cfg = SEVERITY_CONFIG[flag.severity]
        const Icon = cfg.icon
        const isLight = flag.severity === 'medium' || flag.severity === 'low'
        const containerStyle = isLight
          ? {}
          : { background: cfg.bg, borderColor: cfg.border }
        const containerClass = isLight
          ? `rounded-xl border p-4 space-y-3 ${flag.severity === 'medium' ? 'bg-surface-2 border-border' : 'bg-surface-3 border-border'}`
          : 'rounded-xl border p-4 space-y-3'

        return (
          <div
            key={idx}
            className={containerClass}
            style={isLight ? {} : containerStyle}
          >
            {/* Header */}
            <div className="flex items-start gap-3">
              <Icon size={16} style={{ color: cfg.color }} className="mt-0.5 flex-shrink-0" />
              <div className="flex-1 flex flex-wrap items-center gap-2">
                <span className={`text-xs font-mono font-bold uppercase px-1.5 py-0.5 rounded ${cfg.badge}`}>
                  {cfg.label}
                </span>
                <span className="text-xs text-ink-3 font-mono">
                  {TYPE_LABELS[flag.type] ?? flag.type.replace(/_/g, ' ')}
                </span>
              </div>
            </div>

            {/* Message */}
            <p className="text-sm text-ink leading-relaxed pl-7">{flag.message}</p>

            {/* Details */}
            {flag.details && <FlagDetails details={flag.details} flagType={flag.type} />}

            {/* Source attribution */}
            <div className="pl-7 flex flex-wrap gap-2 pt-1 border-t border-border">
              <SourceChip source="open_targets" />
              {(flag.type === 'contradiction' || flag.type === 'corroborated_risk') && (
                <>
                  <SourceChip source="clinicaltrials" />
                  <SourceChip source="uniprot" />
                </>
              )}
              {flag.type === 'safety_flag' && <SourceChip source="uniprot" />}
              {flag.type === 'ip_risk' && <SourceChip source="orange_book" />}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function FlagDetails({ details, flagType }: { details: Record<string, unknown>; flagType: string }) {
  if (flagType === 'contradiction' || flagType === 'corroborated_risk') {
    const failedTrials = details.failed_trials as number | undefined
    const companies = details.companies_that_failed as string[] | undefined
    const lossEstimate = details.total_capital_lost_estimate as string | undefined
    const failureReasons = details.failure_reasons as string[] | undefined
    const trialNames = details.trials_with_liver_toxicity as string[] | undefined

    return (
      <div className="pl-7 grid grid-cols-1 sm:grid-cols-2 gap-2">
        {failedTrials !== undefined && (
          <DetailItem label="Failed / terminated trials" value={String(failedTrials)} />
        )}
        {lossEstimate && (
          <DetailItem label="Estimated capital lost" value={lossEstimate} highlight />
        )}
        {companies && companies.length > 0 && (
          <div className="col-span-2">
            <p className="label-mono mb-1">Companies that failed</p>
            <div className="flex flex-wrap gap-1.5">
              {companies.map((c) => (
                <span key={c} className="text-xs font-mono px-2 py-0.5 rounded bg-surface-2 border border-border text-ink-2">{c}</span>
              ))}
            </div>
          </div>
        )}
        {failureReasons && failureReasons.length > 0 && (
          <div className="col-span-2">
            <p className="label-mono mb-1">Failure reasons on record</p>
            <div className="flex flex-wrap gap-1.5">
              {failureReasons.map((r) => (
                <span key={r} className="text-xs font-mono px-2 py-0.5 rounded bg-surface-2 border border-border text-ink-2">{r}</span>
              ))}
            </div>
          </div>
        )}
        {trialNames && trialNames.length > 0 && (
          <div className="col-span-2">
            <p className="label-mono mb-1">Affected trials</p>
            <div className="flex flex-wrap gap-1.5">
              {trialNames.map((t) => (
                <a
                  key={t}
                  href={`https://clinicaltrials.gov/search?term=${encodeURIComponent(t.split(' ')[0])}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-chip"
                >
                  {t} <ExternalLink size={9} />
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (flagType === 'safety_flag') {
    const organ = details.organ as string | undefined
    const level = details.expression_level as number | undefined
    const mechanism = details.mechanism as string | undefined

    return (
      <div className="pl-7 space-y-2">
        {organ && level !== undefined && (
          <div className="flex items-center gap-4">
            <DetailItem label="Organ" value={organ} />
            <DetailItem label="Expression level" value={`${(level * 100).toFixed(0)}%`} />
          </div>
        )}
        {mechanism && (
          <div>
            <p className="label-mono mb-1">Proposed mechanism</p>
            <p className="text-xs text-ink-2 leading-relaxed">{mechanism}</p>
          </div>
        )}
      </div>
    )
  }

  return null
}

function DetailItem({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="label-mono">{label}</p>
      <p className={`font-mono text-sm ${highlight ? 'text-nogo font-semibold' : 'text-ink-2'}`}>{value}</p>
    </div>
  )
}

function SourceChip({ source }: { source: string }) {
  const labels: Record<string, { label: string; url: string }> = {
    open_targets: { label: 'Open Targets', url: 'https://www.opentargets.org' },
    clinicaltrials: { label: 'ClinicalTrials.gov', url: 'https://clinicaltrials.gov' },
    uniprot: { label: 'UniProt', url: 'https://www.uniprot.org' },
    orange_book: { label: 'FDA Orange Book', url: 'https://www.accessdata.fda.gov/scripts/cder/ob/' },
    pubmed: { label: 'PubMed', url: 'https://pubmed.ncbi.nlm.nih.gov' },
  }
  const meta = labels[source]
  if (!meta) return null
  return (
    <a href={meta.url} target="_blank" rel="noopener noreferrer" className="source-chip">
      {meta.label} <ExternalLink size={9} />
    </a>
  )
}

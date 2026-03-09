import { CheckCircle, AlertCircle, XCircle, ExternalLink } from 'lucide-react'
import type { DataSources } from '../types'

const SOURCE_META: Record<string, { label: string; url: string; description: string }> = {
  open_targets: {
    label: 'Open Targets',
    url: 'https://www.opentargets.org',
    description: 'Genetic associations & tractability',
  },
  clinicaltrials: {
    label: 'ClinicalTrials.gov',
    url: 'https://clinicaltrials.gov',
    description: 'Trial history & outcomes',
  },
  pubmed: {
    label: 'PubMed',
    url: 'https://pubmed.ncbi.nlm.nih.gov',
    description: 'Literature & citations',
  },
  uniprot: {
    label: 'UniProt',
    url: 'https://www.uniprot.org',
    description: 'Protein function & expression',
  },
  fda_drugs: {
    label: 'Drugs@FDA',
    url: 'https://www.accessdata.fda.gov/scripts/cder/daf/',
    description: 'Approved drugs & precedent',
  },
  orange_book: {
    label: 'FDA Orange Book',
    url: 'https://www.accessdata.fda.gov/scripts/cder/ob/',
    description: 'Patents & exclusivities',
  },
}

interface Props {
  sources: DataSources
}

export function DataSourceBar({ sources }: Props) {
  const allSuccess = Object.values(sources).every((s) => s.status === 'success')
  const successCount = Object.values(sources).filter((s) => s.status === 'success').length

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <p className="label-mono">Data sources queried</p>
        <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${
          allSuccess ? 'text-go bg-go-light' : 'text-caution bg-caution-light'
        }`}>
          {successCount}/{Object.keys(sources).length} success
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {Object.entries(SOURCE_META).map(([key, meta]) => {
          const src = sources[key]
          if (!src) return null
          return (
            <a
              key={key}
              href={meta.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-surface-2 border border-border
                         hover:border-teal transition-colors group"
            >
              <StatusIcon status={src.status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <span className="text-xs font-medium text-ink-2 group-hover:text-ink transition-colors truncate">
                    {meta.label}
                  </span>
                  <ExternalLink size={9} className="text-ink-4 group-hover:text-ink-3 flex-shrink-0" />
                </div>
                <p className="text-xs text-ink-3 truncate">{meta.description}</p>
                {src.query_time_ms > 0 && (
                  <p className="font-mono text-xs text-ink-3">{src.query_time_ms}ms</p>
                )}
              </div>
            </a>
          )
        })}
      </div>
      <p className="text-xs text-ink-3 leading-relaxed">
        All claims are sourced directly from the databases above. Click any source to verify data independently.
      </p>
    </div>
  )
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'success') return <CheckCircle size={13} className="text-go mt-0.5 flex-shrink-0" />
  if (status === 'partial') return <AlertCircle size={13} className="text-caution mt-0.5 flex-shrink-0" />
  return <XCircle size={13} className="text-nogo mt-0.5 flex-shrink-0" />
}

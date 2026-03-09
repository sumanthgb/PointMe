import { useState } from 'react'
import { ExternalLink, BookOpen, FlaskConical, Dna, Activity } from 'lucide-react'
import type { ScientificEvidence } from '../types'

interface Props {
  evidence: ScientificEvidence
}

type EvidenceTab = 'genetic' | 'trials' | 'literature' | 'expression' | 'tractability'

export function EvidenceTabs({ evidence }: Props) {
  const [tab, setTab] = useState<EvidenceTab>('genetic')

  const tabs: Array<{ id: EvidenceTab; label: string; icon: React.ElementType }> = [
    { id: 'genetic', label: 'Genetics', icon: Dna },
    { id: 'trials', label: 'Clinical Trials', icon: FlaskConical },
    { id: 'literature', label: 'Literature', icon: BookOpen },
    { id: 'expression', label: 'Expression', icon: Activity },
  ]

  return (
    <div className="card space-y-4">
      <p className="label-mono">Scientific evidence</p>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border overflow-x-auto">
        {tabs.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap
                          transition-colors
                          ${tab === t.id
                            ? 'border-teal text-ink'
                            : 'border-transparent text-ink-3 hover:text-ink-2'
                          }`}
            >
              <Icon size={13} />
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div className="min-h-[200px]">
        {tab === 'genetic' && <GeneticTab genetic={evidence.genetic} />}
        {tab === 'trials' && <TrialsTab trials={evidence.clinical_trials} />}
        {tab === 'literature' && <LiteratureTab literature={evidence.literature} />}
        {tab === 'expression' && <ExpressionTab expression={evidence.expression} />}
      </div>
    </div>
  )
}

function GeneticTab({ genetic }: { genetic: ScientificEvidence['genetic'] }) {
  return (
    <div className="space-y-4">
      {/* Score overview */}
      <div className="flex items-start gap-6">
        <div>
          <p className="label-mono">Genetic association score</p>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono text-3xl font-bold text-teal">{genetic.score.toFixed(2)}</span>
            <span className="text-ink-3 text-sm">/1.00</span>
          </div>
          <ScoreBar value={genetic.score} color="#B8953E" />
        </div>
        <div>
          <p className="label-mono">Total associations</p>
          <span className="font-mono text-2xl font-bold text-ink mt-1 block">{genetic.associations}</span>
        </div>
      </div>

      {/* Source citation */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-3">Source:</span>
        <a
          href="https://www.opentargets.org"
          target="_blank"
          rel="noopener noreferrer"
          className="source-chip"
        >
          Open Targets Platform <ExternalLink size={9} />
        </a>
        <a
          href="https://www.ebi.ac.uk/gwas/"
          target="_blank"
          rel="noopener noreferrer"
          className="source-chip"
        >
          GWAS Catalog <ExternalLink size={9} />
        </a>
      </div>

      {/* Top associations table */}
      {genetic.top_associations.length > 0 && (
        <div>
          <p className="label-mono mb-2">Top associations</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left label-mono py-2 pr-4">Study ID</th>
                  <th className="text-left label-mono py-2 pr-4">Trait</th>
                  <th className="text-left label-mono py-2 pr-4">Source</th>
                  <th className="text-right label-mono py-2">Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {genetic.top_associations.map((a, idx) => (
                  <tr key={idx} className="hover:bg-surface-2 transition-colors">
                    <td className="py-2 pr-4">
                      <a
                        href={`https://www.opentargets.org/evidence?id=${a.study_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-xs text-teal hover:underline flex items-center gap-1"
                      >
                        {a.study_id} <ExternalLink size={9} />
                      </a>
                    </td>
                    <td className="py-2 pr-4 text-ink-2 text-xs">{a.trait}</td>
                    <td className="py-2 pr-4">
                      <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-surface-2 border border-border text-ink-2">
                        {a.source}
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <span className="font-mono text-xs text-teal font-semibold">{a.score.toFixed(2)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <p className="text-xs text-ink-3 leading-relaxed">
        Genetic scores from Open Targets represent the strength of causal evidence linking a gene to a disease,
        integrating GWAS, rare variant, somatic mutation, and functional genomics data.{' '}
        <a
          href="https://platform-docs.opentargets.org/associations"
          target="_blank"
          rel="noopener noreferrer"
          className="text-teal hover:underline"
        >
          Scoring methodology ↗
        </a>
      </p>
    </div>
  )
}

function TrialsTab({ trials }: { trials: ScientificEvidence['clinical_trials'] }) {
  const total = trials.active + trials.completed + trials.failed
  const successRate = trials.success_rate * 100

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Active" value={trials.active} color="#0D4F4F" />
        <StatCard label="Completed" value={trials.completed} color="#2D936C" />
        <StatCard label="Failed / Terminated" value={trials.failed} color="#C1292E" />
        <StatCard label="Success rate" value={`${successRate.toFixed(0)}%`} color={successRate > 60 ? '#2D936C' : successRate > 30 ? '#D4930D' : '#C1292E'} />
      </div>

      {/* Source citation */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-3">Source:</span>
        <a
          href="https://clinicaltrials.gov"
          target="_blank"
          rel="noopener noreferrer"
          className="source-chip"
        >
          ClinicalTrials.gov <ExternalLink size={9} />
        </a>
      </div>

      {/* Phase breakdown */}
      <div>
        <p className="label-mono mb-2">Phase distribution ({total} total)</p>
        <div className="space-y-2">
          {Object.entries(trials.phases).map(([phase, count]) => (
            <div key={phase} className="flex items-center gap-3">
              <span className="font-mono text-xs text-ink-3 w-16 flex-shrink-0">{phase}</span>
              <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${(count / total) * 100}%`, background: '#0D4F4F', opacity: 0.7 + (count / total) * 0.3 }}
                />
              </div>
              <span className="font-mono text-xs text-ink-2 w-6 text-right">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-ink-3">
        Failed/terminated trials include those with status: Terminated, Withdrawn, or Suspended.
        Failure reasons extracted directly from ClinicalTrials.gov NCT records.
      </p>
    </div>
  )
}

function LiteratureTab({ literature }: { literature: ScientificEvidence['literature'] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-6">
        <div>
          <p className="label-mono">Total publications</p>
          <span className="font-mono text-3xl font-bold text-ink mt-1 block">
            {literature.total_papers.toLocaleString()}
          </span>
        </div>
        <div>
          <p className="label-mono">Relevance score</p>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="font-mono text-3xl font-bold text-teal">{literature.relevance_score.toFixed(2)}</span>
            <span className="text-ink-3 text-sm">/1.00</span>
          </div>
          <ScoreBar value={literature.relevance_score} color="#B8953E" />
        </div>
      </div>

      {/* Source citations */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink-3">Source:</span>
        <a href="https://pubmed.ncbi.nlm.nih.gov" target="_blank" rel="noopener noreferrer" className="source-chip">
          PubMed <ExternalLink size={9} />
        </a>
        <a href="https://europepmc.org" target="_blank" rel="noopener noreferrer" className="source-chip">
          Europe PMC <ExternalLink size={9} />
        </a>
      </div>

      {/* Key papers */}
      <div>
        <p className="label-mono mb-2">Key papers</p>
        <div className="space-y-2">
          {literature.key_papers.map((paper) => (
            <div key={paper.pmid} className="p-3 rounded-lg bg-surface-2 border border-border space-y-1.5">
              <div className="flex items-start justify-between gap-3">
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-ink-2 hover:text-teal transition-colors leading-snug flex-1"
                >
                  {paper.title}
                </a>
                <a
                  href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-chip flex-shrink-0"
                >
                  PMID:{paper.pmid} <ExternalLink size={9} />
                </a>
              </div>
              <div className="flex items-center gap-3 text-xs text-ink-3 font-mono">
                {paper.journal && <span>{paper.journal}</span>}
                <span>{paper.year}</span>
                {paper.citation_count > 0 && <span>{paper.citation_count.toLocaleString()} citations</span>}
              </div>
              {paper.abstract && (
                <p className="text-xs text-ink-3 leading-relaxed line-clamp-2">{paper.abstract}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ExpressionTab({ expression }: { expression: ScientificEvidence['expression'] }) {
  const sorted = [...expression.primary_tissues].sort((a, b) => b.level_numeric - a.level_numeric)

  return (
    <div className="space-y-4">
      {/* Function summary */}
      <div>
        <p className="label-mono mb-1.5">Protein function</p>
        <p className="text-sm text-ink-2 leading-relaxed">{expression.function_summary}</p>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs text-ink-3">Source:</span>
          <a
            href="https://www.uniprot.org"
            target="_blank"
            rel="noopener noreferrer"
            className="source-chip"
          >
            UniProt <ExternalLink size={9} />
          </a>
        </div>
      </div>

      {/* Subcellular location */}
      {expression.subcellular_location.length > 0 && (
        <div>
          <p className="label-mono mb-1.5">Subcellular location</p>
          <div className="flex flex-wrap gap-1.5">
            {expression.subcellular_location.map((loc) => (
              <span key={loc} className="text-xs font-mono px-2 py-0.5 rounded bg-surface-2 border border-border text-ink-2">
                {loc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tissue expression bars */}
      <div>
        <p className="label-mono mb-2">Tissue expression profile</p>
        <div className="space-y-2">
          {sorted.map((tissue) => {
            const isSafetyOrgan = ['liver', 'kidney', 'heart', 'lung'].includes(tissue.tissue.toLowerCase())
            const isHigh = tissue.level_numeric >= 0.6
            const color = isSafetyOrgan && isHigh ? '#C1292E' : isHigh ? '#2D936C' : '#9A9A9E'

            return (
              <div key={tissue.tissue} className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 w-24 flex-shrink-0">
                  <span className="font-mono text-xs text-ink-2 capitalize">{tissue.tissue}</span>
                  {isSafetyOrgan && isHigh && (
                    <span className="text-xs text-nogo" title="Safety organ — high expression may indicate toxicity risk">⚠</span>
                  )}
                </div>
                <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${tissue.level_numeric * 100}%`, background: color }}
                  />
                </div>
                <span className="font-mono text-xs w-14 text-right" style={{ color }}>
                  {tissue.level}
                </span>
              </div>
            )
          })}
        </div>
        <p className="text-xs text-ink-3 mt-3">
          ⚠ = Safety organ with high expression. Indicates potential on-target toxicity risk — cross-referenced with clinical trial failure reasons.
        </p>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div className="bg-surface-2 rounded-lg border border-border p-3">
      <p className="label-mono">{label}</p>
      <p className="font-mono text-xl font-bold mt-1" style={{ color }}>
        {value}
      </p>
    </div>
  )
}

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="w-32 h-1.5 bg-surface-3 rounded-full overflow-hidden mt-1">
      <div
        className="h-full rounded-full transition-all duration-1000 ease-out"
        style={{ width: `${value * 100}%`, background: color }}
      />
    </div>
  )
}

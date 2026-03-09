import { CheckCircle, ExternalLink, Clock, DollarSign, Award, ChevronRight } from 'lucide-react'
import type { RegulatoryAssessment } from '../types'

const PATHWAY_META: Record<string, { label: string; desc: string; url: string; color: string }> = {
  '505(b)(1)': {
    label: '505(b)(1) NDA',
    desc: 'Full Data Package — complete pre-clinical and clinical dataset required.',
    url: 'https://www.fda.gov/patients/drug-development-process/step-3-clinical-research',
    color: '#0D4F4F',
  },
  '505(b)(2)': {
    label: '505(b)(2) NDA',
    desc: 'Hybrid Pathway — leverages existing safety/efficacy data from approved drugs.',
    url: 'https://www.fda.gov/media/72222/download',
    color: '#B8953E',
  },
  BLA: {
    label: 'BLA',
    desc: 'Biologics License Application — required for proteins, gene therapies, vaccines.',
    url: 'https://www.fda.gov/vaccines-blood-biologics/development-approval-process-cber/biologics-license-applications-bla-process-cber',
    color: '#2D936C',
  },
}

const DESIGNATION_META: Record<string, { label: string; benefit: string; color: string; url: string }> = {
  fast_track: {
    label: 'Fast Track',
    benefit: 'Rolling review & frequent FDA interactions',
    color: '#0D4F4F',
    url: 'https://www.fda.gov/patients/fast-track-breakthrough-therapy-accelerated-approval-priority-review/fast-track',
  },
  breakthrough_therapy: {
    label: 'Breakthrough Therapy',
    benefit: 'Intensive FDA guidance; compresses timeline 30–50%',
    color: '#2D936C',
    url: 'https://www.fda.gov/patients/fast-track-breakthrough-therapy-accelerated-approval-priority-review/breakthrough-therapy',
  },
  accelerated_approval: {
    label: 'Accelerated Approval',
    benefit: 'Approval on surrogate endpoint; confirmatory trial post-approval',
    color: '#B8953E',
    url: 'https://www.fda.gov/patients/fast-track-breakthrough-therapy-accelerated-approval-priority-review/accelerated-approval',
  },
  priority_review: {
    label: 'Priority Review',
    benefit: '6-month review clock vs. standard 12 months',
    color: '#2D936C',
    url: 'https://www.fda.gov/patients/fast-track-breakthrough-therapy-accelerated-approval-priority-review/priority-review',
  },
  orphan_drug: {
    label: 'Orphan Drug',
    benefit: '7-year market exclusivity + tax credits on clinical costs',
    color: '#D4930D',
    url: 'https://www.fda.gov/industry/developing-products-rare-diseases-conditions/designating-orphan-product-drugs-and-biological-products',
  },
  RMAT: {
    label: 'RMAT',
    benefit: 'Regenerative medicine advanced therapy — expedited review',
    color: '#C1292E',
    url: 'https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/regenerative-medicine-advanced-therapy-designation',
  },
}

// Decision phases with their questions and implications
const DECISION_PHASES = [
  {
    id: 'molecule',
    question: 'Is this a small molecule or biologic?',
    yesLabel: 'Small molecule',
    yesColor: '#0D4F4F',
    noLabel: 'Biologic / gene therapy',
    noColor: '#2D936C',
  },
  {
    id: 'prior_data',
    question: 'Does prior approved drug data exist for this target?',
    yesLabel: 'Yes → 505(b)(2) hybrid pathway',
    yesColor: '#B8953E',
    noLabel: 'No → full data package',
    noColor: '#6A6A6E',
  },
  {
    id: 'rare_disease',
    question: 'Prevalence < 200,000 patients in US?',
    yesLabel: 'Orphan Drug eligible',
    yesColor: '#D4930D',
    noLabel: 'Standard population',
    noColor: '#6A6A6E',
  },
  {
    id: 'unmet_need',
    question: 'Serious condition with unmet medical need?',
    yesLabel: 'Fast Track / Breakthrough eligible',
    yesColor: '#2D936C',
    noLabel: 'Standard review track',
    noColor: '#6A6A6E',
  },
]

interface Props {
  assessment: RegulatoryAssessment
}

export function RegulatoryTree({ assessment }: Props) {
  const pathwayMeta = assessment.recommended_pathway
    ? PATHWAY_META[assessment.recommended_pathway] ?? null
    : null

  const hasDesignations = assessment.special_designations.length > 0
  const isBiologic = assessment.recommended_pathway === 'BLA'
  const isHybrid = assessment.recommended_pathway === '505(b)(2)'
  const hasOrphan = assessment.special_designations.includes('orphan_drug')
  const hasBreakthrough = assessment.special_designations.includes('breakthrough_therapy') || assessment.special_designations.includes('fast_track')

  return (
    <div className="space-y-5">
      {/* Visual decision tree */}
      <div className="card space-y-5">
        <p className="label-mono">Regulatory decision tree</p>

        {/* Decision flow */}
        <div className="space-y-3">
          {/* Node 1: Molecule type */}
          <DecisionNode
            question="Small molecule or biologic?"
            yesLabel="Small molecule"
            noLabel="Biologic / gene therapy"
            activeYes={!isBiologic}
            activeNo={isBiologic}
          />

          {/* Node 2: Prior data */}
          <DecisionNode
            question="Prior approved drug data available for this target?"
            yesLabel="505(b)(2) hybrid — leverage existing data"
            noLabel="505(b)(1) full package — complete new dataset"
            activeYes={isHybrid}
            activeNo={!isBiologic && !isHybrid}
            indent={!isBiologic}
            grayed={isBiologic}
          />

          {/* Node 3: Rare disease */}
          <DecisionNode
            question="Affects fewer than 200,000 US patients?"
            yesLabel="Orphan Drug designation eligible → 7-yr exclusivity"
            noLabel="Standard market size"
            activeYes={hasOrphan}
            activeNo={!hasOrphan}
          />

          {/* Node 4: Unmet need */}
          <DecisionNode
            question="Serious condition with unmet medical need?"
            yesLabel="Fast Track / Breakthrough Therapy eligible"
            noLabel="Standard review track"
            activeYes={hasBreakthrough}
            activeNo={!hasBreakthrough}
          />
        </div>

        {/* Outcome node */}
        <div className="mt-2 pt-4 border-t border-border">
          <div className="flex items-center gap-2 mb-3">
            <ChevronRight size={14} className="text-ink-4" />
            <span className="label-mono">Recommended outcome</span>
          </div>
          <div
            className="flex items-start gap-3 p-4 rounded-xl border"
            style={{ background: (pathwayMeta?.color ?? '#0D4F4F') + '08', borderColor: (pathwayMeta?.color ?? '#0D4F4F') + '30' }}
          >
            <CheckCircle size={16} className="mt-0.5 flex-shrink-0" style={{ color: pathwayMeta?.color ?? '#0D4F4F' }} />
            <div className="flex-1">
              <a
                href={pathwayMeta?.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 group"
              >
                <span className="font-semibold text-base" style={{ color: pathwayMeta?.color ?? '#0D4F4F' }}>
                  {pathwayMeta?.label ?? assessment.recommended_pathway ?? 'Standard NDA'}
                </span>
                <ExternalLink size={11} className="text-ink-4 group-hover:text-teal transition-colors" />
              </a>
              <p className="text-sm text-ink-3 mt-0.5">{pathwayMeta?.desc}</p>
              {hasDesignations && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {assessment.special_designations.map((d) => {
                    const m = DESIGNATION_META[d]
                    return m ? (
                      <span
                        key={d}
                        className="text-xs font-mono px-2 py-0.5 rounded-full border"
                        style={{ color: m.color, borderColor: m.color + '40', background: m.color + '10' }}
                      >
                        {m.label}
                      </span>
                    ) : null
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Timeline / Cost */}
        <div className="grid grid-cols-2 gap-4 pt-3 border-t border-border">
          <div className="flex items-start gap-2">
            <Clock size={14} className="text-ink-4 mt-0.5 flex-shrink-0" />
            <div>
              <p className="label-mono">Estimated timeline</p>
              <p className="font-mono text-sm text-ink mt-1">
                {assessment.estimated_timeline_years ?? 'N/A'}
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <DollarSign size={14} className="text-ink-4 mt-0.5 flex-shrink-0" />
            <div>
              <p className="label-mono">Estimated cost</p>
              <p className="font-mono text-sm text-ink mt-1">
                {assessment.estimated_cost_range ?? 'N/A'}
              </p>
            </div>
          </div>
        </div>
        <a
          href="https://www.fda.gov/industry/user-fees/prescription-drug-user-fee-amendments"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-ink-4 hover:text-teal transition-colors flex items-center gap-1"
        >
          Cost estimates based on Deloitte R&D benchmarks + FDA guidance <ExternalLink size={9} />
        </a>
      </div>

      {/* Clinical development phases */}
      <div className="card space-y-4">
        <p className="label-mono">Clinical development pipeline</p>
        <div className="space-y-2">
          {CLINICAL_PHASES.map((phase, idx) => (
            <PhaseRow key={idx} phase={phase} />
          ))}
        </div>
      </div>

      {/* Special designations */}
      {hasDesignations && (
        <div className="card space-y-3">
          <div className="flex items-center gap-2">
            <Award size={14} className="text-gold" />
            <p className="label-mono">Special designations available</p>
          </div>
          <div className="space-y-2">
            {assessment.special_designations.map((d) => {
              const meta = DESIGNATION_META[d]
              if (!meta) return null
              return (
                <a
                  key={d}
                  href={meta.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-3 p-3 rounded-lg bg-surface-2 border border-border hover:border-teal-border transition-colors group"
                >
                  <div className="w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: meta.color }} />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold" style={{ color: meta.color }}>{meta.label}</span>
                      <ExternalLink size={10} className="text-ink-4 group-hover:text-teal transition-colors" />
                    </div>
                    <p className="text-xs text-ink-3 mt-0.5">{meta.benefit}</p>
                  </div>
                </a>
              )
            })}
          </div>
        </div>
      )}

      {/* Rules engine audit trail */}
      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <p className="label-mono">Rules engine — decision audit trail</p>
          <span className="text-xs text-go font-mono">deterministic · no LLM</span>
        </div>
        <div className="space-y-2">
          {assessment.reasoning.map((rule, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <span className="font-mono text-xs text-ink-4 mt-0.5 flex-shrink-0 w-5">{idx + 1}.</span>
              <p className="text-xs text-ink-3 leading-relaxed">{rule}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-ink-4 italic">
          Pathway is determined by Python rules logic — auditable and reproducible.
          <a
            href="https://www.fda.gov/patients/drug-development-process"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 text-teal underline hover:text-teal/80"
          >
            FDA Drug Development Process ↗
          </a>
        </p>
      </div>
    </div>
  )
}

const CLINICAL_PHASES = [
  { name: 'Pre-clinical', desc: 'In vitro + in vivo safety; IND package preparation', duration: '1–3 years', color: '#6A6A6E' },
  { name: 'IND Filing', desc: 'Investigational New Drug application to FDA', duration: '30-day review', color: '#B8953E' },
  { name: 'Phase I', desc: 'n=20–100, dose escalation, healthy volunteers or patients', duration: '1–2 years', color: '#D4930D' },
  { name: 'Phase II', desc: 'n=100–500, target population, proof-of-concept', duration: '2–4 years', color: '#0D4F4F' },
  { name: 'Phase III', desc: 'n=1,000–5,000+, confirmatory efficacy & safety', duration: '3–6 years', color: '#2D936C' },
  { name: 'NDA / BLA', desc: 'Full data package submission to FDA', duration: '6–12 months', color: '#2D936C' },
  { name: 'FDA Approval', desc: 'Standard 12-month review; 6 months with Priority Review', duration: '6–12 months', color: '#2D936C' },
]

function PhaseRow({ phase }: { phase: typeof CLINICAL_PHASES[0] }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: phase.color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-ink">{phase.name}</span>
          <span className="text-xs text-ink-4 font-mono">{phase.duration}</span>
        </div>
        <p className="text-xs text-ink-3 mt-0.5">{phase.desc}</p>
      </div>
    </div>
  )
}

function DecisionNode({
  question,
  yesLabel,
  noLabel,
  activeYes,
  activeNo,
  indent = false,
  grayed = false,
}: {
  question: string
  yesLabel: string
  noLabel: string
  activeYes: boolean
  activeNo: boolean
  indent?: boolean
  grayed?: boolean
}) {
  return (
    <div className={`${indent ? 'ml-6' : ''} ${grayed ? 'opacity-40' : ''}`}>
      {/* Question box */}
      <div className="bg-surface-2 border border-border rounded-lg px-3 py-2 mb-2">
        <p className="text-xs font-medium text-ink-2">{question}</p>
      </div>
      {/* YES / NO branches */}
      <div className="flex gap-2 ml-3">
        <div
          className={`flex-1 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs transition-all ${
            activeYes
              ? 'bg-go-light border-go-border text-go font-semibold'
              : 'bg-surface-2 border-border text-ink-4'
          }`}
        >
          <span className={`font-mono font-bold text-[10px] ${activeYes ? 'text-go' : 'text-ink-4'}`}>YES</span>
          <span className="ml-1">{yesLabel}</span>
        </div>
        <div
          className={`flex-1 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs transition-all ${
            activeNo
              ? 'bg-surface-3 border-border text-ink-2 font-medium'
              : 'bg-surface-2 border-border text-ink-4'
          }`}
        >
          <span className={`font-mono font-bold text-[10px] ${activeNo ? 'text-ink-3' : 'text-ink-4'}`}>NO</span>
          <span className="ml-1">{noLabel}</span>
        </div>
      </div>
    </div>
  )
}

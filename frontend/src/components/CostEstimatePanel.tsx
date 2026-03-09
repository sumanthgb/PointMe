import { DollarSign, Clock, ExternalLink, ChevronRight } from 'lucide-react'
import type { DevelopmentCostEstimate } from '../types'

function fmtUSD(n: number): string {
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`
  return `$${Math.round(n / 1_000_000)}M`
}

const PHASE_COLORS: Record<string, string> = {
  'preclinical': '#6A6A6E',
  'phase i': '#D4930D',
  'phase ii': '#D4930D',
  'phase iii': '#C1292E',
  'nda': '#0D4F4F',
  'bla': '#0D4F4F',
  'bridging': '#B8953E',
}

function phaseColor(name: string): string {
  const lower = name.toLowerCase()
  for (const [key, color] of Object.entries(PHASE_COLORS)) {
    if (lower.includes(key)) return color
  }
  return '#6A6A6E'
}

interface Props {
  estimate: DevelopmentCostEstimate
}

export function CostEstimatePanel({ estimate }: Props) {
  return (
    <div className="space-y-5">
      {/* MC Percentile summary */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2">
          <DollarSign size={14} className="text-ink-3" />
          <p className="label-mono">Monte Carlo cost estimate — {estimate.pathway} pathway</p>
          <a
            href="https://jamanetwork.com/journals/jama/fullarticle/2552691"
            target="_blank"
            rel="noopener noreferrer"
            className="source-chip ml-auto"
          >
            DiMasi 2016 <ExternalLink size={9} />
          </a>
        </div>

        {/* Cost P10/P50/P90 */}
        <div>
          <p className="label-mono mb-2">Total out-of-pocket cost</p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'P10 (optimistic)', value: estimate.cost_p10_usd, sub: 'best case' },
              { label: 'P50 (median)', value: estimate.cost_p50_usd, sub: 'most likely' },
              { label: 'P90 (conservative)', value: estimate.cost_p90_usd, sub: 'downside' },
            ].map((item) => (
              <div key={item.label} className="bg-surface-2 border border-border rounded-lg p-3 text-center">
                <p className="label-mono mb-1">{item.label}</p>
                <p className="font-mono text-xl font-bold text-ink">{fmtUSD(item.value)}</p>
                <p className="text-[10px] text-ink-4 mt-0.5">{item.sub}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Timeline P10/P50/P90 */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Clock size={12} className="text-ink-3" />
            <p className="label-mono">Total timeline (years to approval)</p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: 'P10', value: estimate.years_p10 },
              { label: 'P50', value: estimate.years_p50 },
              { label: 'P90', value: estimate.years_p90 },
            ].map((item) => (
              <div key={item.label} className="bg-surface-2 border border-border rounded-lg p-3 text-center">
                <p className="label-mono mb-1">{item.label}</p>
                <p className="font-mono text-xl font-bold text-teal">{item.value}y</p>
              </div>
            ))}
          </div>
        </div>

        {estimate.designations_applied.length > 0 && (
          <p className="text-xs text-go bg-go-light border border-go-border rounded-lg px-3 py-2">
            ✓ Timeline compression applied: {estimate.designations_applied.map((d) => d.replace(/_/g, ' ')).join(', ')}
          </p>
        )}
      </div>

      {/* Phase breakdown */}
      <div className="card space-y-3">
        <p className="label-mono">Phase-by-phase breakdown</p>
        <div className="space-y-2">
          {estimate.phases.map((phase, idx) => {
            const color = phaseColor(phase.name)
            return (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 rounded-lg bg-surface-2 border border-border"
                style={{ borderLeftColor: color, borderLeftWidth: 3 }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="text-sm font-medium text-ink">{phase.name}</span>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="font-mono text-xs text-ink-2">
                        {fmtUSD(phase.cost_low_usd)}–{fmtUSD(phase.cost_high_usd)}
                      </span>
                      <span className="font-mono text-xs text-ink-3">
                        {phase.years_low}–{phase.years_high}y
                      </span>
                    </div>
                  </div>
                  {phase.notes && (
                    <p className="text-xs text-ink-4 mt-0.5 leading-relaxed">{phase.notes}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs font-semibold text-ink-2">Total range</span>
          <div className="flex items-center gap-4">
            <span className="font-mono text-sm font-bold text-ink">
              {fmtUSD(estimate.total_cost_low_usd)}–{fmtUSD(estimate.total_cost_high_usd)}
            </span>
            <span className="font-mono text-sm text-ink-3">
              {estimate.total_years_low}–{estimate.total_years_high}y
            </span>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="card space-y-2">
        <div className="flex items-center gap-2">
          <ChevronRight size={12} className="text-ink-4" />
          <p className="label-mono">Cost model summary</p>
        </div>
        <p className="text-xs text-ink-3 leading-relaxed">{estimate.summary}</p>
        <p className="text-xs text-ink-4 italic">
          Out-of-pocket estimates only. Capitalized costs (including cost of capital + portfolio failures) are typically 3–5× higher.{' '}
          <a href="https://www.fda.gov/industry/user-fees/prescription-drug-user-fee-amendments" target="_blank" rel="noopener noreferrer" className="text-teal hover:underline">FDA PDUFA data ↗</a>
        </p>
      </div>
    </div>
  )
}

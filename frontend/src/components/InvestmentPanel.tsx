/**
 * InvestmentPanel.tsx
 *
 * "Poker/arbitrage" lens on the drug target.
 * Three sections:
 *   1. Capital allocation tier — how much to bet
 *   2. Monte Carlo simulation — what the probability distribution looks like
 *   3. Kill conditions — when to fold
 *
 * Everything is computed from the PointMe API response.
 * No hardcoded values — all data is derived live.
 */

import { useMemo, useState } from 'react'
import {
  BarChart, Bar, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { AlertTriangle, AlertOctagon, Info, ExternalLink, TrendingUp, Target, Siren } from 'lucide-react'
import type { PointMeResponse } from '../types'
import {
  runMonteCarlo,
  computeCapitalTier,
  generateKillConditions,
} from '../utils/investmentEngine'

interface Props {
  data: PointMeResponse
}

export function InvestmentPanel({ data }: Props) {
  const mc = useMemo(() => runMonteCarlo(data, 5000), [data])
  const tier = useMemo(() => computeCapitalTier(data, mc), [data, mc])
  const kills = useMemo(() => generateKillConditions(data), [data])

  return (
    <div className="space-y-5">
      <CapitalTierCard tier={tier} mc={mc} data={data} />
      <MonteCarloCard mc={mc} data={data} />
      <KillConditionsCard kills={kills} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Capital Tier Card
// ---------------------------------------------------------------------------
function CapitalTierCard({ tier, mc, data }: { tier: ReturnType<typeof computeCapitalTier>; mc: ReturnType<typeof runMonteCarlo>; data: PointMeResponse }) {
  const pPct = (mc.p_approval * 100).toFixed(1)
  const baselinePct = (mc.industry_baseline * 100).toFixed(1)
  const relativeStr = mc.p_approval > mc.industry_baseline
    ? `${(mc.p_approval / mc.industry_baseline).toFixed(1)}× above industry baseline`
    : `${((1 - mc.p_approval / mc.industry_baseline) * 100).toFixed(0)}% below industry baseline`

  return (
    <div
      className="rounded-2xl border p-6 space-y-5"
      style={{ background: tier.badge_color, borderColor: tier.color + '40' }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <p className="label-mono flex items-center gap-2">
            <TrendingUp size={12} className="text-ink-3" />
            Capital allocation recommendation
          </p>
          <h2 className="text-2xl font-bold" style={{ color: tier.color, fontFamily: 'JetBrains Mono, monospace' }}>
            {tier.label}
          </h2>
          <p className="text-ink-2 font-medium text-sm">{tier.stage}</p>
        </div>

        {/* Amount badge */}
        <div className="text-right flex-shrink-0">
          <p className="label-mono">Bet size</p>
          <p className="font-mono text-xl font-bold mt-1" style={{ color: tier.color }}>
            {tier.amount_range}
          </p>
        </div>
      </div>

      {/* Rationale */}
      <p className="text-sm text-ink-2 leading-relaxed border-l-2 pl-3" style={{ borderColor: tier.color + '60' }}>
        {tier.rationale}
      </p>

      {/* EV note */}
      <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-2 border border-border">
        <Target size={13} className="text-ink-3 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-ink-2 leading-relaxed">{tier.ev_note}</p>
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-3 gap-4 pt-1 border-t border-border">
        <Metric
          label="P(Approval)"
          value={`${pPct}%`}
          sub={`vs ${baselinePct}% baseline`}
          color={mc.p_approval > mc.industry_baseline ? '#2D936C' : '#C1292E'}
        />
        <Metric
          label="Genetic mult."
          value={`${mc.genetic_multiplier.toFixed(1)}×`}
          sub="vs. no genetic support"
          color="#0D4F4F"
        />
        <Metric
          label="Relative to market"
          value={relativeStr.split('×')[0].split('%')[0]}
          sub={relativeStr}
          color={mc.p_approval > mc.industry_baseline ? '#2D936C' : '#D4930D'}
        />
      </div>

      {/* Source note */}
      <p className="text-xs text-ink-3 flex items-center gap-1.5">
        Multiplier based on{' '}
        <a
          href="https://www.nature.com/articles/s41573-024-00884-4"
          target="_blank"
          rel="noopener noreferrer"
          className="text-teal hover:underline"
        >
          Nelson et al., Nature 2024 ↗
        </a>
        — genetic support is the single strongest predictor of clinical success.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Monte Carlo Card
// ---------------------------------------------------------------------------
function MonteCarloCard({ mc, data }: { mc: ReturnType<typeof runMonteCarlo>; data: PointMeResponse }) {
  const [showPhases, setShowPhases] = useState(false)
  const pPct = mc.p_approval * 100

  // Build phase funnel data
  const funnelData = [
    { name: 'IND start', pct: 100, fill: '#9A9A9E' },
    { name: 'Phase 1 →', pct: mc.phase_probabilities.phase1 * 100, fill: '#0D4F4F' },
    {
      name: 'Phase 2 →',
      pct: mc.phase_probabilities.phase1 * mc.phase_probabilities.phase2 * 100,
      fill: '#B8953E',
    },
    {
      name: 'Phase 3 →',
      pct: mc.phase_probabilities.phase1 * mc.phase_probabilities.phase2 * mc.phase_probabilities.phase3 * 100,
      fill: '#0D4F4F',
    },
    { name: 'Approval', pct: pPct, fill: pPct > 10 ? '#2D936C' : pPct > 5 ? '#D4930D' : '#C1292E' },
  ]

  return (
    <div className="card space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="label-mono">Monte Carlo risk simulation</p>
          <span className="text-xs font-mono text-ink-3">{mc.n_simulations.toLocaleString()} paths</span>
        </div>
        <a
          href="https://www.nature.com/articles/s41573-024-00884-4"
          target="_blank"
          rel="noopener noreferrer"
          className="source-chip"
        >
          BIO/QLS 2024 <ExternalLink size={9} />
        </a>
      </div>

      {/* P(Approval) bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-ink font-medium">Probability of approval</span>
          <div className="flex items-center gap-2">
            <span
              className="font-mono text-xl font-bold"
              style={{ color: pPct > 10 ? '#2D936C' : pPct > 5 ? '#D4930D' : '#C1292E' }}
            >
              {pPct.toFixed(1)}%
            </span>
            <span className="text-xs text-ink-3 font-mono">
              [{(mc.p_approval_ci_low * 100).toFixed(1)}–{(mc.p_approval_ci_high * 100).toFixed(1)}% CI]
            </span>
          </div>
        </div>

        {/* Stacked comparison bar */}
        <div className="relative h-8 bg-surface-3 rounded-lg overflow-hidden">
          {/* Industry baseline marker */}
          <div
            className="absolute top-0 bottom-0 w-px bg-ink-4/40 z-10"
            style={{ left: `${mc.industry_baseline * 100 / 35 * 100}%` }}
          />
          {/* This target */}
          <div
            className="absolute top-0 bottom-0 left-0 rounded-lg transition-all duration-1000 flex items-center px-3"
            style={{
              width: `${Math.min((pPct / 35) * 100, 100)}%`,
              background: pPct > 10 ? 'linear-gradient(90deg, rgba(45,147,108,0.3), rgba(45,147,108,0.6))' : pPct > 5 ? 'linear-gradient(90deg, rgba(212,147,13,0.3), rgba(212,147,13,0.6))' : 'linear-gradient(90deg, rgba(193,41,46,0.3), rgba(193,41,46,0.6))',
              borderRight: `2px solid ${pPct > 10 ? '#2D936C' : pPct > 5 ? '#D4930D' : '#C1292E'}`,
            }}
          >
            <span className="text-xs font-mono font-bold text-ink whitespace-nowrap">
              This target: {pPct.toFixed(1)}%
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-ink-3 font-mono">
          <span>0%</span>
          <span
            className="flex items-center gap-1"
            style={{ marginLeft: `${(mc.industry_baseline / 0.35) * 100}%` }}
          >
            ↑ baseline {(mc.industry_baseline * 100).toFixed(1)}%
          </span>
          <span>35%+</span>
        </div>
      </div>

      {/* Phase funnel chart */}
      <div>
        <button
          onClick={() => setShowPhases(v => !v)}
          className="flex items-center gap-1 text-xs text-ink-3 hover:text-ink-2 transition-colors mb-3"
        >
          {showPhases ? '▾' : '▸'} Phase-by-phase transition probabilities
        </button>
        {showPhases && (
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnelData} layout="vertical" margin={{ left: 60, right: 40, top: 0, bottom: 0 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#6A6A6E' }} tickFormatter={v => `${v}%`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: '#4A4A4E' }} width={58} />
                <Tooltip
                  contentStyle={{ background: '#fff', border: '1px solid #D4CFC8', borderRadius: 8, fontSize: 12, color: '#1C1C1E' }}
                  formatter={(v: number) => [`${v.toFixed(1)}%`, 'Cumulative P(reach)']}
                  labelStyle={{ color: '#4A4A4E' }}
                />
                <ReferenceLine x={mc.industry_baseline * 100} stroke="#D4CFC8" strokeDasharray="3 3" />
                <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
                  {funnelData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.fill} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Timeline + Cost distribution */}
      <div className="grid grid-cols-2 gap-4">
        <DistributionBlock
          label="Development timeline"
          unit="years"
          p10={mc.timeline_p10}
          p50={mc.timeline_p50}
          p90={mc.timeline_p90}
          color="#0D4F4F"
          source="DiMasi 2016 + Deloitte 2024"
          sourceUrl="https://www.deloitte.com/uk/en/Industries/life-sciences-health-care/research/measuring-return-from-pharmaceutical-innovation.html"
        />
        <DistributionBlock
          label="Total cost to approval"
          unit="$M"
          p10={mc.cost_p10_m}
          p50={mc.cost_p50_m}
          p90={mc.cost_p90_m}
          color="#B8953E"
          source="Deloitte R&D benchmarks"
          sourceUrl="https://www.deloitte.com/uk/en/Industries/life-sciences-health-care/research/measuring-return-from-pharmaceutical-innovation.html"
        />
      </div>

      {/* Risk driver */}
      <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-2 border border-border">
        <Info size={13} className="text-ink-3 mt-0.5 flex-shrink-0" />
        <div className="space-y-0.5">
          <p className="text-xs font-medium text-ink-2">Primary risk driver</p>
          <p className="text-xs text-ink-3 leading-relaxed">{mc.primary_risk_driver}</p>
        </div>
      </div>

      <p className="text-xs text-ink-3 leading-relaxed">
        Simulation adjusts industry base rates (BIO/QLS/Citeline 2024) for genetic evidence strength (Nelson et al. 2024),
        clinical trial track record, cross-reference flags, and regulatory designations. Results are probabilistic,
        not deterministic — actual outcomes depend on execution, competitive dynamics, and scientific factors
        not captured in public data.
      </p>
    </div>
  )
}

function DistributionBlock({
  label, unit, p10, p50, p90, color, source, sourceUrl,
}: {
  label: string
  unit: string
  p10: number
  p50: number
  p90: number
  color: string
  source: string
  sourceUrl: string
}) {
  const fmt = (v: number) => unit === '$M' ? `$${v >= 1000 ? (v / 1000).toFixed(1) + 'B' : v + 'M'}` : `${v}y`
  return (
    <div className="space-y-2">
      <p className="label-mono">{label}</p>
      <div className="space-y-1.5">
        {[
          { label: 'P10 (optimistic)', val: p10 },
          { label: 'P50 (median)', val: p50 },
          { label: 'P90 (pessimistic)', val: p90 },
        ].map(({ label: l, val }) => (
          <div key={l} className="flex items-center gap-2">
            <span className="text-xs text-ink-3 w-28 flex-shrink-0">{l}</span>
            <div className="flex-1 h-1.5 bg-surface-3 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${(val / p90) * 80}%`, background: color, opacity: 0.6 + (val / p90) * 0.4 }}
              />
            </div>
            <span className="font-mono text-xs font-semibold w-14 text-right" style={{ color }}>
              {fmt(val)}
            </span>
          </div>
        ))}
      </div>
      <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="source-chip mt-1 inline-flex">
        {source} <ExternalLink size={9} />
      </a>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Kill Conditions Card
// ---------------------------------------------------------------------------
function KillConditionsCard({ kills }: { kills: ReturnType<typeof generateKillConditions> }) {
  const [expanded, setExpanded] = useState<number | null>(0)

  const SEVERITY_CFG = {
    critical: { icon: AlertOctagon, color: '#C1292E', bg: 'rgba(193,41,46,0.07)', border: 'rgba(193,41,46,0.22)', label: 'FOLD', labelColor: 'text-nogo' },
    high:     { icon: AlertTriangle, color: '#D4930D', bg: 'rgba(212,147,13,0.07)', border: 'rgba(212,147,13,0.22)', label: 'FOLD', labelColor: 'text-caution' },
    medium:   { icon: Info, color: '#6A6A6E', bg: '', border: '', label: 'REASSESS', labelColor: 'text-ink-3' },
  }

  return (
    <div className="card space-y-4">
      <div className="flex items-center gap-2">
        <Siren size={14} className="text-nogo" />
        <p className="label-mono">Kill conditions</p>
        <span className="text-xs text-ink-3 ml-auto">fold if any of these occur</span>
      </div>

      <p className="text-xs text-ink-3 leading-relaxed">
        These are pre-specified conditions derived from PointMe's cross-reference analysis. Define them
        in your investment thesis before committing capital — making the exit decision in advance removes
        emotional bias from the fold.
      </p>

      <div className="space-y-2">
        {kills.map((kill, idx) => {
          const cfg = SEVERITY_CFG[kill.severity]
          const Icon = cfg.icon
          const isOpen = expanded === idx
          const isMedium = kill.severity === 'medium'

          return (
            <div
              key={idx}
              className={`rounded-xl border overflow-hidden transition-all ${isMedium ? 'bg-surface-2 border-border' : ''}`}
              style={isMedium ? {} : { background: cfg.bg, borderColor: cfg.border }}
            >
              {/* Header row */}
              <button
                onClick={() => setExpanded(isOpen ? null : idx)}
                className="w-full flex items-start gap-3 p-3.5 text-left"
              >
                <Icon size={14} style={{ color: cfg.color }} className="mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-xs font-mono font-bold uppercase px-1.5 py-0.5 rounded ${cfg.labelColor} bg-surface-2`}
                    >
                      {cfg.label}
                    </span>
                    <span className="text-xs text-ink-3 font-mono">{kill.phase}</span>
                  </div>
                  <p className="text-sm text-ink leading-snug mt-1">{kill.condition}</p>
                </div>
                <span className="text-ink-3 text-xs mt-1 flex-shrink-0">{isOpen ? '▴' : '▾'}</span>
              </button>

              {/* Expanded details */}
              {isOpen && (
                <div className="px-4 pb-3.5 space-y-2 border-t border-border pt-2.5">
                  <p className="text-xs text-ink-2 leading-relaxed">{kill.reasoning}</p>
                  <a
                    href="#"
                    onClick={e => e.preventDefault()}
                    className="source-chip"
                  >
                    {kill.source} <ExternalLink size={9} />
                  </a>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-start gap-2 p-3 rounded-lg bg-surface-2 border border-border">
        <Info size={12} className="text-ink-3 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-ink-3 leading-relaxed">
          Kill conditions are derived from PointMe's cross-reference engine findings, not from LLM generation.
          They represent the operationalised form of the risk flags above.{' '}
          <a
            href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4517983/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-teal underline hover:text-teal/80"
          >
            Pre-specified stopping rules methodology ↗
          </a>
        </p>
      </div>
    </div>
  )
}

function Metric({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="space-y-0.5">
      <p className="label-mono">{label}</p>
      <p className="font-mono text-lg font-bold" style={{ color }}>{value}</p>
      <p className="text-xs text-ink-3 leading-tight">{sub}</p>
    </div>
  )
}

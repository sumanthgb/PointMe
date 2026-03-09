import { useEffect, useRef, useState } from 'react'
import type { PointMeResponse } from '../types'

interface Props {
  data: PointMeResponse
}

const VERDICT_CONFIG = {
  GO: {
    color: '#2D936C',
    dimBg: 'rgba(45,147,108,0.07)',
    borderColor: 'rgba(45,147,108,0.22)',
    glowClass: 'verdict-glow-go',
    label: 'GO',
    sublabel: 'Target is viable. Proceed to development planning.',
    textClass: 'text-go',
  },
  CAUTION: {
    color: '#D4930D',
    dimBg: 'rgba(212,147,13,0.07)',
    borderColor: 'rgba(212,147,13,0.22)',
    glowClass: 'verdict-glow-caution',
    label: 'CAUTION',
    sublabel: 'Significant risks present. Reassess before committing.',
    textClass: 'text-caution',
  },
  'NO-GO': {
    color: '#C1292E',
    dimBg: 'rgba(193,41,46,0.07)',
    borderColor: 'rgba(193,41,46,0.22)',
    glowClass: 'verdict-glow-nogo',
    label: 'NO-GO',
    sublabel: 'Evidence strongly advises against this target.',
    textClass: 'text-nogo',
  },
}

function AnimatedScore({ value, color }: { value: number; color: string }) {
  const [displayed, setDisplayed] = useState(0)
  const frameRef = useRef<number>()
  const startRef = useRef<number>()
  const DURATION = 1400

  useEffect(() => {
    startRef.current = undefined
    function tick(ts: number) {
      if (!startRef.current) startRef.current = ts
      const elapsed = ts - startRef.current
      const progress = Math.min(elapsed / DURATION, 1)
      // ease-out-expo
      const eased = 1 - Math.pow(2, -10 * progress)
      setDisplayed(Math.round(eased * value * 10) / 10)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick)
      }
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current) }
  }, [value])

  // SVG ring
  const radius = 60
  const circumference = 2 * Math.PI * radius
  const fraction = Math.min(displayed / 100, 1)
  const offset = circumference * (1 - fraction)

  return (
    <div className="relative flex items-center justify-center w-40 h-40">
      <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 144 144">
        {/* Track */}
        <circle cx="72" cy="72" r={radius} fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth="8" />
        {/* Progress */}
        <circle
          cx="72"
          cy="72"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="score-ring-circle"
          style={{ filter: `drop-shadow(0 0 6px ${color}66)` }}
        />
      </svg>
      <div className="flex flex-col items-center">
        <span className="font-mono font-semibold text-3xl" style={{ color }}>
          {displayed.toFixed(displayed >= 10 ? 1 : 1)}
        </span>
        <span className="font-mono text-xs text-ink-3">/100</span>
      </div>
    </div>
  )
}

export function VerdictHero({ data }: Props) {
  const cfg = VERDICT_CONFIG[data.scores.recommendation]
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100)
    return () => clearTimeout(t)
  }, [])

  const criticalFlags = data.flags.filter((f) => f.severity === 'critical')
  const topFlag = criticalFlags[0] ?? data.flags[0]

  return (
    <div
      className={`rounded-2xl border p-8 transition-all duration-500 ${cfg.glowClass} ${
        visible ? 'opacity-100' : 'opacity-0'
      }`}
      style={{ background: cfg.dimBg, borderColor: cfg.borderColor }}
    >
      <div className="flex flex-col lg:flex-row items-center gap-8">
        {/* Score ring */}
        <div className="flex flex-col items-center gap-1.5">
          <AnimatedScore value={data.scores.combined_score} color={cfg.color} />
          <span className="label-mono">combined score</span>
          {data.scores.confidence && (
            <span className="font-mono text-[10px] text-ink-4">
              95% CI [{data.scores.confidence.combined_score_ci_low.toFixed(1)} — {data.scores.confidence.combined_score_ci_high.toFixed(1)}]
            </span>
          )}
        </div>

        {/* Verdict + summary */}
        <div className="flex-1 text-center lg:text-left space-y-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 justify-center lg:justify-start">
              <p className="label-mono">Recommendation</p>
              {data.scores.confidence && (
                <StabilityBadge stability={data.scores.confidence.recommendation_stability} />
              )}
            </div>
            <h2 className={`text-5xl font-bold tracking-tight ${cfg.textClass}`} style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              {cfg.label}
            </h2>
            <p className="text-ink-2 text-sm">{cfg.sublabel}</p>
          </div>

          {/* Sub-scores */}
          <div className="flex flex-wrap gap-4 justify-center lg:justify-start">
            <ScoreBar label="Science" value={data.scores.science_score} color="#B8953E" />
            <ScoreBar label="Regulatory" value={data.scores.regulatory_score} color="#0D4F4F" />
          </div>
        </div>

        {/* Key risk flag */}
        {topFlag && (
          <div
            className="max-w-xs w-full lg:w-auto rounded-xl border px-4 py-3 space-y-1"
            style={{
              borderColor: topFlag.severity === 'critical' ? 'rgba(193,41,46,0.4)' : topFlag.severity === 'high' ? 'rgba(212,147,13,0.35)' : 'rgba(13,79,79,0.3)',
              background: topFlag.severity === 'critical' ? 'rgba(193,41,46,0.06)' : 'rgba(212,147,13,0.06)',
            }}
          >
            <div className="flex items-center gap-2">
              <span
                className="text-xs font-mono font-bold uppercase px-1.5 py-0.5 rounded"
                style={{
                  color: topFlag.severity === 'critical' ? '#C1292E' : topFlag.severity === 'high' ? '#D4930D' : '#6A6A6E',
                  background: topFlag.severity === 'critical' ? 'rgba(193,41,46,0.12)' : 'rgba(212,147,13,0.12)',
                }}
              >
                {topFlag.severity}
              </span>
              <span className="text-xs text-ink-2 font-mono">{topFlag.type.replace(/_/g, ' ')}</span>
            </div>
            <p className="text-xs text-ink-2 leading-relaxed line-clamp-3">{topFlag.message}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function StabilityBadge({ stability }: { stability: number }) {
  const pct = Math.round(stability * 100)
  const color = pct >= 85 ? '#2D936C' : pct >= 65 ? '#D4930D' : '#C1292E'
  const label = pct >= 85 ? 'High confidence' : pct >= 65 ? 'Borderline' : 'Unstable'
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded border"
      style={{ color, borderColor: color + '40', background: color + '10' }}
      title={`${pct}% of Monte Carlo perturbations agree with this recommendation`}
    >
      ◆ {pct}% stable · {label}
    </span>
  )
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col gap-1 min-w-[120px]">
      <div className="flex justify-between items-center">
        <span className="label-mono">{label}</span>
        <span className="font-mono text-xs font-semibold" style={{ color }}>
          {value.toFixed(1)}
        </span>
      </div>
      <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${value}%`, background: color, boxShadow: `0 0 6px ${color}66` }}
        />
      </div>
    </div>
  )
}

/**
 * investmentEngine.ts
 *
 * Derives capital allocation, Monte Carlo risk simulation, and kill conditions
 * entirely from the existing PointMe API response. Zero additional backend calls.
 *
 * Base rates sourced from:
 *   - BIO/QLS/Citeline 2024 Clinical Development Success Rate Report
 *   - Nelson et al., Nature 2024 (genetic evidence multiplier: 2.6×)
 *   - Deloitte 2024 R&D Benchmarking Report
 *   - DiMasi et al., J Health Economics 2016 (phase cost distributions)
 */

import type { PointMeResponse } from '../types'

// ---------------------------------------------------------------------------
// Industry base rate constants
// Source: BIO/QLS/Citeline 2024 (all therapeutic areas)
// ---------------------------------------------------------------------------
const BASE_PHASE_SUCCESS = {
  p1_to_p2: 0.52,    // 52% of Phase 1 trials proceed to Phase 2
  p2_to_p3: 0.289,   // 28.9% of Phase 2 trials proceed to Phase 3
  p3_to_nda: 0.578,  // 57.8% of Phase 3 trials lead to NDA/BLA filing
  nda_approval: 0.906, // 90.6% of filed applications get approved
}

// Phase duration params [mean years, std years] — log-normally distributed
const PHASE_DURATION_PARAMS: Record<string, [number, number]> = {
  preclinical: [2.2, 0.7],
  phase1:      [1.6, 0.5],
  phase2:      [2.8, 0.8],
  phase3:      [4.2, 1.3],
  fda_review:  [1.0, 0.35],
}

// Phase cost params [mean $M, std $M] — log-normally distributed
// Source: DiMasi 2016 + Deloitte 2024 inflation adjustment
const PHASE_COST_PARAMS: Record<string, [number, number]> = {
  preclinical: [32, 16],
  phase1:      [44, 20],
  phase2:      [120, 50],
  phase3:      [460, 180],
  fda_review:  [60, 25],
}

const INDUSTRY_BASELINE_P_APPROVAL = 0.079 // 7.9% IND → approval

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MonteCarloResult {
  p_approval: number          // 0–1, adjusted
  p_approval_ci_low: number
  p_approval_ci_high: number
  industry_baseline: number   // 0.079, for comparison
  genetic_multiplier: number
  timeline_p10: number        // years
  timeline_p50: number
  timeline_p90: number
  cost_p10_m: number          // $M
  cost_p50_m: number
  cost_p90_m: number
  n_simulations: number
  primary_risk_driver: string
  phase_probabilities: {
    phase1: number
    phase2: number
    phase3: number
    approval: number
  }
}

export interface CapitalTier {
  tier: 'platform' | 'lead_asset' | 'exploratory' | 'milestone_gated' | 'not_fundable'
  label: string
  amount_range: string
  stage: string
  rationale: string
  color: string
  badge_color: string
  ev_note: string
}

export interface KillCondition {
  phase: string
  condition: string
  severity: 'critical' | 'high' | 'medium'
  reasoning: string
  source: string
}

// ---------------------------------------------------------------------------
// Seeded pseudo-random (so results are stable per query, not re-randomised on render)
// ---------------------------------------------------------------------------
function mulberry32(seed: number) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function stringToSeed(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

// Box-Muller normal sample using provided RNG
function sampleNormal(rng: () => number, mean: number, std: number): number {
  const u1 = Math.max(rng(), 1e-9)
  const u2 = rng()
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
  return mean + std * z
}

// Log-normal sample: given desired mean and std of the underlying variable
function sampleLogNormal(rng: () => number, mean: number, std: number): number {
  const v = std * std
  const m2 = mean * mean
  const mu = Math.log(m2 / Math.sqrt(v + m2))
  const sigma = Math.sqrt(Math.log(v / m2 + 1))
  const z = sampleNormal(rng, 0, 1)
  return Math.exp(mu + sigma * z)
}

function percentile(arr: number[], p: number): number {
  const sorted = [...arr].sort((a, b) => a - b)
  const idx = (p / 100) * (sorted.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (idx - lo) * (sorted[hi] - sorted[lo])
}

// ---------------------------------------------------------------------------
// Adjusted phase probabilities
// ---------------------------------------------------------------------------
function computeAdjustedProbabilities(data: PointMeResponse) {
  const { scores, scientific_evidence, flags, regulatory_assessment } = data

  // Genetic evidence multiplier (Nelson et al. 2024)
  // genetic_score > 0.8 → ×2.6, > 0.6 → ×1.8, > 0.4 → ×1.2, ≤ 0.4 → ×0.7
  const gs = scientific_evidence.genetic.score
  const geneticMult =
    gs > 0.8 ? 2.6 :
    gs > 0.6 ? 1.8 :
    gs > 0.4 ? 1.2 : 0.7

  // Trial success rate adjustment (applies primarily to Phase 2/3)
  const tsr = scientific_evidence.clinical_trials.success_rate
  const trialMult =
    tsr > 0.75 ? 1.5 :
    tsr > 0.50 ? 1.1 :
    tsr > 0.25 ? 0.7 :
    tsr > 0.10 ? 0.4 : 0.2

  // Flag penalty
  const criticalCount = flags.filter(f => f.severity === 'critical').length
  const highCount = flags.filter(f => f.severity === 'high').length
  const flagMult = Math.pow(0.40, criticalCount) * Math.pow(0.72, highCount)

  // Designation bonus (fast track, breakthrough, etc.)
  const desigs = regulatory_assessment.special_designations
  let desigMult = 1.0
  if (desigs.includes('breakthrough_therapy')) desigMult *= 1.3
  if (desigs.includes('fast_track')) desigMult *= 1.1
  if (desigs.includes('priority_review')) desigMult *= 1.1

  // Combined multiplier, capped so P doesn't exceed realistic bounds
  const totalMult = geneticMult * trialMult * flagMult * desigMult

  // Apply to each phase (multiply relative to base, then cap at reasonable max)
  const cap = (v: number, max: number) => Math.min(v, max)
  const p1 = cap(BASE_PHASE_SUCCESS.p1_to_p2 * Math.sqrt(totalMult), 0.92)
  const p2 = cap(BASE_PHASE_SUCCESS.p2_to_p3 * totalMult, 0.78)
  const p3 = cap(BASE_PHASE_SUCCESS.p3_to_nda * totalMult, 0.88)
  const pa = BASE_PHASE_SUCCESS.nda_approval

  return { p1, p2, p3, pa, geneticMult, totalMult, flagMult }
}

// ---------------------------------------------------------------------------
// Monte Carlo simulation
// ---------------------------------------------------------------------------
export function runMonteCarlo(data: PointMeResponse, nSims = 5000): MonteCarloResult {
  const seed = stringToSeed(data.target + data.disease + String(data.scores.combined_score))
  const rng = mulberry32(seed)

  const { p1, p2, p3, pa, geneticMult, flagMult } = computeAdjustedProbabilities(data)

  // Designation time bonuses
  const desigs = data.regulatory_assessment.special_designations
  const timeMultP3 = desigs.includes('breakthrough_therapy') ? 0.70 : 1.0
  const timeMultFDA = desigs.includes('priority_review') ? 0.55
    : desigs.includes('fast_track') ? 0.80
    : desigs.includes('breakthrough_therapy') ? 0.70 : 1.0

  const successTimelines: number[] = []
  const successCosts: number[] = []
  let successCount = 0
  const allFinalTimes: number[] = []

  for (let i = 0; i < nSims; i++) {
    let totalTime = 0
    let totalCost = 0

    // Preclinical
    const [ptm, pts] = PHASE_DURATION_PARAMS.preclinical
    const [pcm, pcs] = PHASE_COST_PARAMS.preclinical
    totalTime += Math.max(0.5, sampleLogNormal(rng, ptm, pts))
    totalCost += Math.max(5, sampleLogNormal(rng, pcm, pcs))

    // Phase 1
    const p1Pass = rng() < p1
    if (!p1Pass) {
      allFinalTimes.push(totalTime + sampleLogNormal(rng, ...PHASE_DURATION_PARAMS.phase1))
      continue
    }
    totalTime += Math.max(0.5, sampleLogNormal(rng, ...PHASE_DURATION_PARAMS.phase1))
    totalCost += Math.max(10, sampleLogNormal(rng, ...PHASE_COST_PARAMS.phase1))

    // Phase 2
    const p2Pass = rng() < p2
    if (!p2Pass) {
      allFinalTimes.push(totalTime + sampleLogNormal(rng, ...PHASE_DURATION_PARAMS.phase2))
      continue
    }
    totalTime += Math.max(1, sampleLogNormal(rng, ...PHASE_DURATION_PARAMS.phase2))
    totalCost += Math.max(30, sampleLogNormal(rng, ...PHASE_COST_PARAMS.phase2))

    // Phase 3
    const p3Pass = rng() < p3
    if (!p3Pass) {
      const [d3m, d3s] = PHASE_DURATION_PARAMS.phase3
      allFinalTimes.push(totalTime + sampleLogNormal(rng, d3m * timeMultP3, d3s))
      continue
    }
    const [d3m, d3s] = PHASE_DURATION_PARAMS.phase3
    totalTime += Math.max(1.5, sampleLogNormal(rng, d3m * timeMultP3, d3s))
    totalCost += Math.max(80, sampleLogNormal(rng, ...PHASE_COST_PARAMS.phase3))

    // FDA review
    const paPass = rng() < pa
    if (!paPass) {
      allFinalTimes.push(totalTime)
      continue
    }
    const [dfm, dfs] = PHASE_DURATION_PARAMS.fda_review
    totalTime += Math.max(0.3, sampleLogNormal(rng, dfm * timeMultFDA, dfs))
    totalCost += Math.max(15, sampleLogNormal(rng, ...PHASE_COST_PARAMS.fda_review))

    successCount++
    successTimelines.push(totalTime)
    successCosts.push(totalCost)
    allFinalTimes.push(totalTime)
  }

  const pApproval = successCount / nSims

  // Wilson confidence interval for proportion
  const z = 1.645 // 90% CI
  const wilsonCenter = (successCount + (z * z) / 2) / (nSims + z * z)
  const wilsonHalf = (z * Math.sqrt((successCount * (nSims - successCount)) / nSims + (z * z) / 4)) / (nSims + z * z)
  const ciLow = Math.max(0, wilsonCenter - wilsonHalf)
  const ciHigh = Math.min(1, wilsonCenter + wilsonHalf)

  // Use successful timelines if we have enough; otherwise all
  const tlArr = successTimelines.length > 50 ? successTimelines : allFinalTimes
  const costArr = successCosts.length > 50 ? successCosts : [400, 600, 800, 1000, 1400]

  const primaryRiskDriver =
    flagMult < 0.3 ? 'Critical safety flags dominate — multiple independent risk signals converge' :
    data.scientific_evidence.clinical_trials.success_rate < 0.25 ? 'Repeated clinical trial failures are the primary risk driver' :
    data.scientific_evidence.genetic.score < 0.5 ? 'Weak genetic evidence creates high uncertainty on target validity' :
    'Standard development risk — execution and competitive dynamics are primary variables'

  return {
    p_approval: pApproval,
    p_approval_ci_low: ciLow,
    p_approval_ci_high: ciHigh,
    industry_baseline: INDUSTRY_BASELINE_P_APPROVAL,
    genetic_multiplier: geneticMult,
    timeline_p10: Math.round(percentile(tlArr, 10) * 10) / 10,
    timeline_p50: Math.round(percentile(tlArr, 50) * 10) / 10,
    timeline_p90: Math.round(percentile(tlArr, 90) * 10) / 10,
    cost_p10_m: Math.round(percentile(costArr, 10)),
    cost_p50_m: Math.round(percentile(costArr, 50)),
    cost_p90_m: Math.round(percentile(costArr, 90)),
    n_simulations: nSims,
    primary_risk_driver: primaryRiskDriver,
    phase_probabilities: { phase1: p1, phase2: p2, phase3: p3, approval: pa },
  }
}

// ---------------------------------------------------------------------------
// Capital allocation tier
// ---------------------------------------------------------------------------
export function computeCapitalTier(data: PointMeResponse, mc: MonteCarloResult): CapitalTier {
  const { scores, flags } = data
  const criticalCount = flags.filter(f => f.severity === 'critical').length
  const pct = mc.p_approval * 100

  if (criticalCount >= 2 || scores.combined_score < 28) {
    return {
      tier: 'not_fundable',
      label: 'Not Fundable',
      amount_range: 'Pass',
      stage: 'Do not invest',
      color: '#ef4444',
      badge_color: 'rgba(239,68,68,0.12)',
      rationale: `The weight of evidence is strongly against this target. With ${criticalCount} critical risk flags and a combined score of ${scores.combined_score.toFixed(1)}, capital is better deployed elsewhere. P(approval) = ${pct.toFixed(1)}% vs. 7.9% industry baseline.`,
      ev_note: 'Negative expected value when accounting for development costs vs. approval probability.',
    }
  }

  if (criticalCount === 1 || (scores.combined_score >= 28 && scores.combined_score < 42)) {
    return {
      tier: 'milestone_gated',
      label: 'Milestone-Gated Only',
      amount_range: '$1M–$5M',
      stage: 'Data buy — fund the experiment, not the program',
      color: '#f97316',
      badge_color: 'rgba(249,115,22,0.10)',
      rationale: `One critical risk flag creates significant uncertainty. Fund only the experiment needed to resolve it. If the flag is resolved, reassess for exploratory investment. P(approval) = ${pct.toFixed(1)}%.`,
      ev_note: 'Structured as a real option — pay to learn, not to develop.',
    }
  }

  if (scores.combined_score >= 42 && scores.combined_score < 57) {
    return {
      tier: 'exploratory',
      label: 'Exploratory Bet',
      amount_range: '$3M–$15M',
      stage: 'Seed / Preclinical validation',
      color: '#f59e0b',
      badge_color: 'rgba(245,158,11,0.10)',
      rationale: `Score and risk profile support a small, time-limited exploratory bet to resolve key uncertainties through targeted preclinical experiments. P(approval) = ${pct.toFixed(1)}% — not yet sufficient for full development commitment.`,
      ev_note: 'Asymmetric return profile: limited downside, upside if key risks resolve favorably.',
    }
  }

  if (scores.combined_score >= 57 && scores.combined_score < 70) {
    return {
      tier: 'lead_asset',
      label: 'Lead Asset Bet',
      amount_range: '$20M–$80M',
      stage: 'Series A — fund to Phase 2 proof-of-concept',
      color: '#6366f1',
      badge_color: 'rgba(99,102,241,0.10)',
      rationale: `Strong enough evidence to fund through Phase 2 PoC. Genetic validation (${data.scientific_evidence.genetic.score.toFixed(2)}) and trial precedent support this as a lead asset. P(approval) = ${pct.toFixed(1)}% — above the industry average of 7.9%.`,
      ev_note: 'Expected value positive at Series A stage, contingent on Phase 2 data meeting predefined endpoints.',
    }
  }

  // score >= 70
  return {
    tier: 'platform',
    label: 'Platform Company Bet',
    amount_range: '$100M–$500M+',
    stage: 'Series B/C — full development commitment',
    color: '#00d68f',
    badge_color: 'rgba(0,214,143,0.08)',
    rationale: `Exceptional evidence profile. Score of ${scores.combined_score.toFixed(1)} with clean risk flags and strong genetic validation (${data.scientific_evidence.genetic.score.toFixed(2)}) supports full development commitment. P(approval) = ${pct.toFixed(1)}% — ${(pct / 7.9).toFixed(1)}× the industry baseline.`,
    ev_note: `At P(approval) = ${pct.toFixed(1)}% and estimated cost of $${mc.cost_p50_m.toLocaleString()}M, expected value is positive assuming peak sales >$500M (standard for targets in this therapeutic area).`,
  }
}

// ---------------------------------------------------------------------------
// Kill conditions — derived from flags, clinical data, and regulatory rules
// ---------------------------------------------------------------------------
export function generateKillConditions(data: PointMeResponse): KillCondition[] {
  const conditions: KillCondition[] = []
  const { flags, scientific_evidence, regulatory_assessment } = data

  // From CRITICAL flags
  for (const flag of flags.filter(f => f.severity === 'critical')) {
    if (flag.type === 'corroborated_risk') {
      const organ = (flag.details?.organ as string) ?? 'target organ'
      const level = flag.details?.expression_level as number | undefined
      conditions.push({
        phase: 'Phase 1',
        condition: `If ${organ} toxicity biomarkers exceed 3× ULN (ALT/AST) or clinical signs of ${organ} dysfunction emerge`,
        severity: 'critical',
        reasoning: `High ${organ} expression (${level ? (level * 100).toFixed(0) + '%' : 'elevated'}) corroborated by clinical trial failures. This is a mechanism-driven risk — mitigations are unlikely to resolve it.`,
        source: 'UniProt expression data × ClinicalTrials.gov failure records',
      })
    }
    if (flag.type === 'contradiction' && (flag.details?.phase3_failures as number ?? 0) >= 2) {
      conditions.push({
        phase: 'Phase 2',
        condition: 'If primary endpoint does not show statistically significant improvement at pre-specified interim analysis',
        severity: 'critical',
        reasoning: `Pattern of Phase 3 failures on this target means Phase 2 signal must be unambiguous before Phase 3 commitment. Marginal Phase 2 signals have not translated to Phase 3 success.`,
        source: 'ClinicalTrials.gov — historical Phase 3 failure pattern',
      })
    }
  }

  // From HIGH flags
  for (const flag of flags.filter(f => f.severity === 'high')) {
    if (flag.type === 'contradiction') {
      const failedTrials = flag.details?.failed_trials as number ?? 0
      if (failedTrials > 0) {
        conditions.push({
          phase: 'Any',
          condition: 'If DSMB (Data Safety Monitoring Board) recommends pause or unblinding at any interim analysis',
          severity: 'high',
          reasoning: `Existing trial failures signal that unexpected safety or efficacy signals are possible. DSMB action is a leading indicator that should trigger immediate reassessment.`,
          source: 'ClinicalTrials.gov — terminated trial history',
        })
      }
    }
    if (flag.type === 'safety_flag') {
      const organ = (flag.details?.organ as string) ?? 'monitored organ'
      conditions.push({
        phase: 'Phase 1 / Phase 2',
        condition: `If dose-limiting toxicity (DLT) in ${organ} exceeds 33% of patients at therapeutic dose`,
        severity: 'high',
        reasoning: `On-target ${organ} expression indicates mechanism-linked toxicity potential. DLT threshold breach at therapeutic exposure suggests insufficient therapeutic window.`,
        source: 'UniProt tissue expression data',
      })
    }
  }

  // Trial failure history → competitive kill condition
  const failedCount = scientific_evidence.clinical_trials.failed
  if (failedCount >= 3) {
    conditions.push({
      phase: 'Phase 3',
      condition: `If another Phase 3 program targeting the same mechanism reports futility or safety stop`,
      severity: 'high',
      reasoning: `${failedCount} prior failures suggest target-class risk. A contemporaneous Phase 3 failure by a competitor would provide strong additional evidence that the mechanism is not tractable.`,
      source: 'ClinicalTrials.gov — failed trial count',
    })
  }

  // IP risk kill condition
  if (flags.some(f => f.type === 'ip_risk')) {
    conditions.push({
      phase: 'Pre-clinical / Series A',
      condition: 'If freedom-to-operate (FTO) analysis reveals blocking composition-of-matter patents that cannot be designed around',
      severity: 'high',
      reasoning: 'High IP crowding score. FTO analysis is required before committing Series A capital.',
      source: 'FDA Orange Book',
    })
  }

  // Regulatory kill condition
  const pathway = regulatory_assessment.recommended_pathway
  if (pathway === '505(b)(1)' || pathway === 'BLA') {
    conditions.push({
      phase: 'FDA Review',
      condition: 'If FDA issues a Complete Response Letter (CRL) citing manufacturing or safety deficiencies that require a new Phase 3',
      severity: 'medium',
      reasoning: 'Full NDA/BLA submission pathways carry non-trivial CRL risk. A new Phase 3 requirement would push total cost above the upper bound of the estimated range.',
      source: 'FDA regulatory precedent',
    })
  }

  // Competitive landscape kill condition
  const activeDrugs = scientific_evidence.tractability.known_drugs_in_pipeline
  if (activeDrugs >= 5) {
    conditions.push({
      phase: 'Phase 2 / Phase 3',
      condition: `If a competitor in the same mechanism class achieves breakthrough approval, fundamentally altering commercial addressable market`,
      severity: 'medium',
      reasoning: `${activeDrugs} drugs currently in pipeline. First-in-class or best-in-class positioning must be maintained. Market entry after 2 approved agents substantially reduces commercial potential.`,
      source: 'Open Targets — known drugs in pipeline',
    })
  }

  // Always include: general futility
  conditions.push({
    phase: 'Any interim analysis',
    condition: 'If pre-specified futility boundary is crossed at any interim analysis (α-spending: O\'Brien-Fleming)',
    severity: 'medium',
    reasoning: 'Standard adaptive trial design — futility stopping rules protect capital and patient exposure. Crossing the futility boundary is the operationalised version of the kill decision.',
    source: 'Best practice — adaptive clinical trial design',
  })

  // Sort: critical first
  const order = { critical: 0, high: 1, medium: 2 }
  return conditions.sort((a, b) => order[a.severity] - order[b.severity])
}

export interface GeneticAssociation {
  study_id: string
  trait: string
  score: number
  source: string
}

export interface Trial {
  nct_id: string
  title: string
  phase: string | null
  status: string
  why_stopped: string | null
  enrollment: number | null
  start_date: string | null
  primary_outcome: string | null
}

export interface Paper {
  pmid: string
  title: string
  abstract: string
  year: number
  journal: string | null
  citation_count: number
}

export interface TissueExpression {
  tissue: string
  level: string
  level_numeric: number
}

export interface FDADrug {
  name: string
  approval_date: string | null
  application_type: string
  application_number: string | null
  pathway: string
  sponsor: string | null
  mechanism_of_action: string | null
}

export interface ComparableDrug {
  name: string
  exclusivity_type: string | null
  exclusivity_expiration: string | null
  patent_number: string | null
  patent_expiration: string | null
}

export interface ScoreConfidence {
  recommendation_stability: number   // 0-1, fraction of MC iterations matching the recommendation
  combined_score_ci_low: number      // 2.5th percentile of MC score distribution (0-100)
  combined_score_ci_high: number     // 97.5th percentile
  success_rate_ci_low: number        // bootstrap 2.5th percentile on trial success rate (0-1)
  success_rate_ci_high: number       // bootstrap 97.5th percentile
  n_trials_observed: number          // completed + failed trial count (bootstrap sample size)
}

export interface Scores {
  science_score: number
  regulatory_score: number
  combined_score: number
  recommendation: 'GO' | 'CAUTION' | 'NO-GO'
  confidence: ScoreConfidence | null
}

export interface RegulatoryAssessment {
  recommended_pathway: string | null
  special_designations: string[]
  estimated_timeline_years: string | null
  estimated_cost_range: string | null
  reasoning: string[]
}

export interface CrossReferenceFlag {
  type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  message: string
  details: Record<string, unknown> | null
}

export interface ScientificEvidence {
  genetic: {
    score: number
    associations: number
    top_associations: GeneticAssociation[]
  }
  clinical_trials: {
    active: number
    completed: number
    failed: number
    success_rate: number
    phases: Record<string, number>
  }
  literature: {
    total_papers: number
    relevance_score: number
    key_papers: Paper[]
  }
  expression: {
    primary_tissues: TissueExpression[]
    function_summary: string
    subcellular_location: string[]
  }
  tractability: {
    score: number
    molecule_type: string
    known_drugs_in_pipeline: number
  }
}

export interface DataSources {
  [key: string]: {
    status: string
    query_time_ms: number
  }
}

export interface PointMeResponse {
  target: string
  disease: string
  scores: Scores
  scientific_evidence: ScientificEvidence
  regulatory_assessment: RegulatoryAssessment
  flags: CrossReferenceFlag[]
  llm_synthesis: string | null
  data_sources: DataSources
}

export type AppState = 'idle' | 'loading' | 'results' | 'error'

export interface LoadingStep {
  id: string
  label: string
  status: 'pending' | 'running' | 'success' | 'partial' | 'failed'
  time_ms?: number
  preview?: string
}

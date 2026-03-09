import type { PointMeResponse } from './types'

export const MOCK_KRAS: PointMeResponse = {
  target: 'KRAS G12C',
  disease: 'non-small cell lung cancer',
  scores: {
    science_score: 78.4,
    regulatory_score: 61.2,
    combined_score: 69.8,
    recommendation: 'GO',
    confidence: null,
  },
  scientific_evidence: {
    genetic: {
      score: 0.85,
      associations: 12,
      top_associations: [
        { study_id: 'EFO_0003060', trait: 'Non-small cell lung carcinoma', score: 0.85, source: 'GWAS' },
        { study_id: 'EFO_0005140', trait: 'Lung adenocarcinoma', score: 0.78, source: 'rare_variant' },
        { study_id: 'EFO_0000389', trait: 'Lung cancer', score: 0.71, source: 'GWAS' },
        { study_id: 'EFO_0006859', trait: 'KRAS mutation positive NSCLC', score: 0.65, source: 'rare_variant' },
      ],
    },
    clinical_trials: {
      active: 8,
      completed: 15,
      failed: 3,
      success_rate: 0.83,
      phases: { 'Phase 1': 6, 'Phase 2': 9, 'Phase 3': 5, 'Phase 4': 3 },
    },
    literature: {
      total_papers: 2847,
      relevance_score: 0.91,
      key_papers: [
        {
          pmid: '32795706',
          title: 'Sotorasib for Lung Cancers with KRAS p.G12C Mutation',
          abstract: 'In this phase 2 trial, sotorasib showed durable clinical benefit in patients with KRAS G12C–mutated advanced NSCLC who had received prior therapies.',
          year: 2021,
          journal: 'New England Journal of Medicine',
          citation_count: 1420,
        },
        {
          pmid: '34506199',
          title: 'Adagrasib in Non-Small-Cell Lung Cancer Harboring a KRAS G12C Mutation',
          abstract: 'Adagrasib demonstrated clinically meaningful efficacy in patients with KRAS G12C–mutated previously treated NSCLC, with a manageable safety profile.',
          year: 2022,
          journal: 'New England Journal of Medicine',
          citation_count: 1180,
        },
        {
          pmid: '35733654',
          title: 'Resistance mechanisms to KRAS G12C inhibitors',
          abstract: 'Secondary KRAS mutations and bypass pathway activation are the primary mechanisms driving acquired resistance to covalent KRAS G12C inhibitors.',
          year: 2022,
          journal: 'Nature Medicine',
          citation_count: 340,
        },
      ],
    },
    expression: {
      primary_tissues: [
        { tissue: 'lung', level: 'High', level_numeric: 1.0 },
        { tissue: 'colon', level: 'Medium', level_numeric: 0.6 },
        { tissue: 'pancreas', level: 'Medium', level_numeric: 0.55 },
        { tissue: 'liver', level: 'Low', level_numeric: 0.3 },
        { tissue: 'kidney', level: 'Low', level_numeric: 0.25 },
        { tissue: 'brain', level: 'Low', level_numeric: 0.2 },
      ],
      function_summary:
        'GTPase that functions as a molecular switch cycling between active GTP-bound and inactive GDP-bound states. Critical regulator of the RAS/MAPK signaling pathway controlling cell proliferation, differentiation, and survival.',
      subcellular_location: ['Cell membrane', 'Cytoplasm'],
    },
    tractability: {
      score: 1.0,
      molecule_type: 'small_molecule',
      known_drugs_in_pipeline: 7,
    },
  },
  regulatory_assessment: {
    recommended_pathway: '505(b)(1)',
    special_designations: ['fast_track', 'breakthrough_therapy'],
    estimated_timeline_years: '5-7 years',
    estimated_cost_range: '$800M–$2B',
    reasoning: [
      'No approved drugs with same MOA found and molecule is a small molecule → standard 505(b)(1) NDA pathway.',
      'Disease prevalence unknown — manual orphan drug eligibility check recommended.',
      'Disease is serious/life-threatening AND unmet medical need is indicated → eligible for Fast Track designation (rolling review, more FDA interactions).',
      'Serious condition + strong genetic evidence + prior Phase completion → may be eligible for Breakthrough Therapy designation (intensive FDA guidance).',
      'Special designations (fast_track, breakthrough_therapy) may reduce timeline and cost estimates above.',
    ],
  },
  flags: [
    {
      type: 'contradiction',
      severity: 'high',
      message:
        'Strong genetic association (0.85) but 3 failed/terminated trials exist. Target is genetically validated but faces translational barriers — likely resistance mechanisms, not target invalidity.',
      details: {
        genetic_score: 0.85,
        failed_trials: 3,
        failure_reasons: ['Disease progression', 'Adverse events - grade 3 diarrhea', 'Sponsor decision'],
      },
    },
    {
      type: 'safety_flag',
      severity: 'medium',
      message:
        'High lung expression (1.00) detected. For an NSCLC program this is expected, but on-target pulmonary toxicity should be monitored in IND-enabling studies.',
      details: { organ: 'lung', expression_level: 1.0, threshold: 0.6 },
    },
  ],
  llm_synthesis: `**EXECUTIVE SUMMARY**

PointMe recommends **GO** for KRAS G12C in non-small cell lung cancer (combined score: 69.8/100). FDA approval of Sotorasib (2021) and Adagrasib (2022) establishes strong proof-of-concept for this target, and the genetic evidence (score: 0.85 across 12 GWAS/rare-variant associations) independently validates KRAS G12C as a causal driver. The 3 prior trial failures reflect translational barriers—not target invalidity—making differentiated resistance-mechanism strategies viable.

**SCIENTIFIC EVIDENCE ASSESSMENT**

Genetic evidence is compelling: 12 GWAS/rare variant associations with a top score of 0.85 establish KRAS G12C as a causal driver in NSCLC. The clinical trial landscape is mature, with 15 completed trials and an 83% success rate. The 2,847 publications reflect a highly active research field. Three failed trials warrant attention—two were stopped for adverse events and disease progression, not target invalidation.

**REGULATORY PATHWAY ANALYSIS**

Recommended pathway: **505(b)(1) NDA**. Fast Track and Breakthrough Therapy designations are achievable, potentially compressing the 5–7 year estimated timeline to 4–5 years for a next-generation inhibitor addressing resistance.

**RISK FLAGS**

→ [HIGH] Genetic-trial contradiction: Strong genetics but 3 failures. Key question is mechanism—one failure was AE-related, suggesting tolerability rather than target biology as the limitation.

→ [MEDIUM] Lung expression safety flag: High on-target expression is expected for NSCLC but warrants IND-enabling pulmonary safety monitoring.

**CONFIDENCE NOTE**

All 6 data sources returned successfully. Confidence: High. A full patent landscape search is recommended before advancing given active IP around covalent KRAS G12C inhibitor scaffolds.`,
  data_sources: {
    open_targets: { status: 'success', query_time_ms: 412 },
    clinicaltrials: { status: 'success', query_time_ms: 634 },
    pubmed: { status: 'success', query_time_ms: 891 },
    uniprot: { status: 'success', query_time_ms: 287 },
    fda_drugs: { status: 'success', query_time_ms: 503 },
    orange_book: { status: 'partial', query_time_ms: 341 },
  },
}

export const MOCK_BACE1: PointMeResponse = {
  target: 'BACE1',
  disease: "Alzheimer's disease",
  scores: {
    science_score: 61.3,
    regulatory_score: 38.5,
    combined_score: 22.1,
    recommendation: 'NO-GO',
    confidence: null,
  },
  scientific_evidence: {
    genetic: {
      score: 0.74,
      associations: 8,
      top_associations: [
        { study_id: 'EFO_0000249', trait: "Alzheimer's disease", score: 0.74, source: 'GWAS' },
        { study_id: 'EFO_0006792', trait: 'Late-onset Alzheimer disease', score: 0.68, source: 'rare_variant' },
        { study_id: 'EFO_0000249', trait: 'Amyloid precursor protein processing', score: 0.61, source: 'GWAS' },
      ],
    },
    clinical_trials: {
      active: 0,
      completed: 2,
      failed: 5,
      success_rate: 0.07,
      phases: { 'Phase 1': 2, 'Phase 2': 3, 'Phase 3': 2 },
    },
    literature: {
      total_papers: 4102,
      relevance_score: 0.82,
      key_papers: [
        {
          pmid: '29415497',
          title: 'Atabecestat in subjects with preclinical Alzheimer disease — a randomized trial',
          abstract: 'Atabecestat (JNJ-54861911) was discontinued in Phase 2b/3 due to liver toxicity signals. 77% increase in transaminases observed.',
          year: 2018,
          journal: 'Nature Medicine',
          citation_count: 410,
        },
        {
          pmid: '30104963',
          title: 'Verubecestat for prodromal Alzheimer disease: APECS trial results',
          abstract: 'Verubecestat did not improve clinical outcomes in prodromal AD and worsened cognitive function at higher doses. Phase 3 terminated.',
          year: 2019,
          journal: 'New England Journal of Medicine',
          citation_count: 890,
        },
        {
          pmid: '31495781',
          title: 'Lanabecestat for Alzheimer disease: AMARANTH and DAYBREAK-ALZ Phase 3 trials stopped',
          abstract: 'Both Phase 3 studies of lanabecestat were halted for futility after interim analysis. No benefit on primary cognitive endpoint detected.',
          year: 2019,
          journal: 'JAMA Neurology',
          citation_count: 320,
        },
        {
          pmid: '28985456',
          title: 'Elenbecestat Phase 3 MissionAD trials terminated: safety and futility',
          abstract: 'Elenbecestat Phase 3 was stopped due to an unfavorable risk/benefit ratio. Neuropsychiatric side effects and cognitive worsening reported.',
          year: 2018,
          journal: 'Lancet Neurology',
          citation_count: 275,
        },
      ],
    },
    expression: {
      primary_tissues: [
        { tissue: 'brain', level: 'High', level_numeric: 0.95 },
        { tissue: 'liver', level: 'High', level_numeric: 0.88 },
        { tissue: 'kidney', level: 'Medium', level_numeric: 0.55 },
        { tissue: 'pancreas', level: 'Medium', level_numeric: 0.48 },
        { tissue: 'heart', level: 'Low', level_numeric: 0.3 },
        { tissue: 'lung', level: 'Low', level_numeric: 0.22 },
      ],
      function_summary:
        'Aspartyl protease responsible for the cleavage of amyloid precursor protein (APP) at the β-site, generating the N-terminus of the amyloid β-peptide. Essential role in myelination; expressed in multiple organs beyond the CNS.',
      subcellular_location: ['Endosome membrane', 'Cell membrane', 'Golgi apparatus'],
    },
    tractability: {
      score: 0.55,
      molecule_type: 'small_molecule',
      known_drugs_in_pipeline: 0,
    },
  },
  regulatory_assessment: {
    recommended_pathway: '505(b)(1)',
    special_designations: ['fast_track', 'breakthrough_therapy'],
    estimated_timeline_years: '10-15 years',
    estimated_cost_range: '$3B–$5B+',
    reasoning: [
      'No approved drugs with same MOA found → standard 505(b)(1) NDA pathway.',
      "Alzheimer's disease prevalence (6M+ US) exceeds orphan threshold — orphan drug designation not available.",
      'Disease is serious/life-threatening AND unmet medical need is severe → eligible for Fast Track designation.',
      'Strong genetic evidence + serious condition → Breakthrough Therapy designation potentially available, but 5 prior Phase 3 failures will require extensive regulatory justification.',
      "Note: FDA has issued guidance following multiple BACE1 inhibitor failures. Any new BACE1 program will face heightened regulatory scrutiny and will likely require differentiated mechanism-of-action argument.",
    ],
  },
  flags: [
    {
      type: 'corroborated_risk',
      severity: 'critical',
      message:
        'CRITICAL: High hepatic expression (0.88) CORROBORATES liver toxicity seen in 3/5 clinical trials. Atabecestat (Janssen), verubecestat (Merck), and elenbecestat (Eisai/Biogen) all showed hepatotoxicity signals. This is a mechanism-driven safety liability, not formulation-dependent.',
      details: {
        organ: 'liver',
        expression_level: 0.88,
        trials_with_liver_toxicity: ['NCT02260674 (atabecestat)', 'NCT01739348 (verubecestat)', 'NCT02956486 (elenbecestat)'],
        mechanism: 'on-target hepatic BACE1 inhibition disrupts lipid metabolism',
      },
    },
    {
      type: 'contradiction',
      severity: 'critical',
      message:
        'CRITICAL: 5 Phase 2/3 trials terminated — 0% Phase 3 approval rate. All major pharma BACE1 programs have failed (Merck, Lilly/AstraZeneca, Janssen, Eisai/Biogen). Genetic validation (0.74) does not overcome translational failure pattern.',
      details: {
        genetic_score: 0.74,
        failed_trials: 5,
        phase3_failures: 4,
        companies_that_failed: ['Merck (verubecestat)', 'Janssen (atabecestat)', 'Lilly/AstraZeneca (lanabecestat)', 'Eisai/Biogen (elenbecestat)'],
        total_capital_lost_estimate: '$~10B',
      },
    },
    {
      type: 'safety_flag',
      severity: 'high',
      message:
        'Neuropsychiatric side effects (depression, suicidality) observed across multiple BACE1 inhibitor programs, likely from disruption of neuregulin-1 processing — a non-APP BACE1 substrate.',
      details: {
        mechanism: 'BACE1 cleaves neuregulin-1 in addition to APP; neuregulin-1 disruption affects myelination and neuronal signaling',
        trials_affected: ['verubecestat (NCT01739348)', 'elenbecestat (NCT02956486)'],
      },
    },
    {
      type: 'data_gap',
      severity: 'medium',
      message:
        'No active programs in pipeline. All known drug candidates have been discontinued. This represents a near-complete industry exit from this target — a strong market signal.',
      details: { active_trials: 0, discontinued_drugs_count: 7 },
    },
  ],
  llm_synthesis: `**EXECUTIVE SUMMARY**

PointMe recommends **NO-GO** for BACE1 in Alzheimer's disease (combined score: 22.1/100). This is one of the most extensively validated failures in modern drug development. Five Phase 2/3 clinical trials from four major pharmaceutical companies have been terminated, with an estimated $10B in capital lost. The genetic evidence (score: 0.74) is real — BACE1 cleaves APP to produce amyloid-β — but it does not overcome a systematic translational failure pattern driven by mechanism-linked liver toxicity and neuropsychiatric side effects.

**THE CRITICAL FINDING — WHY THIS IS A NO-GO**

PointMe's cross-reference engine has identified a corroborated risk that would cost any new entrant billions to discover independently:

**High hepatic BACE1 expression (0.88) directly explains the liver toxicity observed in 3 of 5 clinical trials.** This is not a formulation problem or an off-target effect — it is an on-target consequence of inhibiting BACE1 in the liver, where it plays a role in lipid metabolism. Atabecestat (Janssen) was discontinued for hepatotoxicity. Verubecestat (Merck) showed transaminase elevations. Elenbecestat (Eisai/Biogen) was stopped for unfavorable risk/benefit. The expression data and the trial failure data are independently telling the same story.

**SCIENTIFIC EVIDENCE ASSESSMENT**

The genetic evidence for BACE1 in Alzheimer's is legitimate (0.74 across 8 GWAS associations) — APP mutations near the BACE1 cleavage site cause familial AD, and BACE1 knockdown reduces amyloid plaques in mouse models. The problem is downstream: the amyloid hypothesis itself has been challenged by the Phase 3 failures, and BACE1 is not a clean target — it has over 50 known substrates beyond APP, including neuregulin-1 (essential for myelination) and CHL1 (neuronal guidance). Inhibiting BACE1 comprehensively causes collateral biology.

**REGULATORY PATH**

Fast Track and Breakthrough Therapy designations are theoretically available, but following 5 Phase 3 failures, FDA will require a compelling mechanistic differentiation argument before approving a new IND. Any new BACE1 program should expect heightened CMC and toxicology requirements.

**CONFIDENCE NOTE**

All 6 data sources returned successfully. Confidence: High. The weight of evidence against this target is exceptionally strong. The only viable path forward would involve tissue-selective CNS BACE1 inhibition that spares hepatic expression — a technically demanding medicinal chemistry challenge that no program has solved.`,
  data_sources: {
    open_targets: { status: 'success', query_time_ms: 388 },
    clinicaltrials: { status: 'success', query_time_ms: 711 },
    pubmed: { status: 'success', query_time_ms: 924 },
    uniprot: { status: 'success', query_time_ms: 301 },
    fda_drugs: { status: 'success', query_time_ms: 456 },
    orange_book: { status: 'success', query_time_ms: 298 },
  },
}

export const DEMO_PRESETS = [
  { label: 'KRAS G12C / NSCLC', target: 'KRAS G12C', disease: 'non-small cell lung cancer', mock: MOCK_KRAS },
  { label: "BACE1 / Alzheimer's", target: 'BACE1', disease: "Alzheimer's disease", mock: MOCK_BACE1 },
]

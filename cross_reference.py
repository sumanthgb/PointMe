"""
engine/cross_reference.py — Cross-Reference Engine

Detects contradictions and safety flags by comparing outputs across all 6 workers.
This is the key differentiator for TargetIQ — algorithmic, not LLM-generated.

Each check either appends a CrossReferenceFlag or stays silent.
Flags have severity: low / medium / high / critical
"""

from models import (
    CrossReferenceFlag, FlagSeverity, FlagType,
    OpenTargetsResult, ClinicalTrialsResult, UniProtResult,
    FDADrugsResult, OrangeBookResult, PubMedResult
)
from config import (
    EXPRESSION_SAFETY_THRESHOLD,
    SAFETY_ORGANS,
    GENETIC_CONTRADICTION_THRESHOLD,
    MIN_FAILED_TRIALS_FOR_FLAG,
)


def _get_organ_expression(uniprot: UniProtResult, organ: str) -> float:
    """Look up numeric expression level for a given organ/tissue."""
    organ_lower = organ.lower()
    for te in uniprot.tissue_expression:
        if organ_lower in te.tissue.lower():
            return te.level_numeric
    return 0.0


def cross_reference(
    open_targets: OpenTargetsResult,
    trials: ClinicalTrialsResult,
    pubmed: PubMedResult,
    uniprot: UniProtResult,
    fda_drugs: FDADrugsResult,
    orange_book: OrangeBookResult,
) -> list[CrossReferenceFlag]:
    """
    Run all cross-reference checks across worker outputs.

    Returns:
        List of CrossReferenceFlag objects, ordered by severity (critical first).
    """
    flags: list[CrossReferenceFlag] = []

    # -------------------------------------------------------------------
    # CHECK 1: Strong genetic evidence BUT prior trial failures
    # Logic: genetics says target is valid, but trials disagree → contradiction
    # -------------------------------------------------------------------
    failed_count = len(trials.failed_trials)
    if (open_targets.genetic_score > GENETIC_CONTRADICTION_THRESHOLD
            and failed_count >= MIN_FAILED_TRIALS_FOR_FLAG):

        failure_reasons = [
            t.why_stopped for t in trials.failed_trials if t.why_stopped
        ]
        flags.append(CrossReferenceFlag(
            type=FlagType.CONTRADICTION,
            severity=FlagSeverity.HIGH,
            message=(
                f"Strong genetic association (score: {open_targets.genetic_score:.2f}) "
                f"but {failed_count} failed/terminated trial(s) exist. "
                "Target may be validated genetically but face translational barriers."
            ),
            details={
                "genetic_score": open_targets.genetic_score,
                "failed_trials": failed_count,
                "failure_reasons": failure_reasons[:5],  # cap for payload size
            }
        ))

    # -------------------------------------------------------------------
    # CHECK 2: High expression in safety-critical organs → toxicity risk
    # Logic: if target is highly expressed in liver/heart/kidney/brain/lung,
    #        on-target toxicity is a real concern
    # -------------------------------------------------------------------
    for organ in SAFETY_ORGANS:
        expression_level = _get_organ_expression(uniprot, organ)
        if expression_level >= EXPRESSION_SAFETY_THRESHOLD:
            flags.append(CrossReferenceFlag(
                type=FlagType.SAFETY_FLAG,
                severity=FlagSeverity.MEDIUM,
                message=(
                    f"High {organ} expression detected (level: {expression_level:.2f}) "
                    f"→ potential on-target {organ} toxicity risk requires monitoring."
                ),
                details={
                    "organ": organ,
                    "expression_level": expression_level,
                    "threshold": EXPRESSION_SAFETY_THRESHOLD,
                }
            ))

    # -------------------------------------------------------------------
    # CHECK 3: Trial failure reason corroborated by expression data
    # Logic: trial failed for organ toxicity AND we see high expression in that organ
    # This is the CRITICAL flag — two independent data sources say the same thing
    # -------------------------------------------------------------------
    toxicity_organ_keywords = {
        "liver":  ["hepatotox", "liver", "hepatic", "alt", "ast", "jaundice"],
        "heart":  ["cardiotox", "cardiac", "qt prolongation", "arrhythmia", "ejection"],
        "kidney": ["nephrotox", "renal", "creatinine", "kidney"],
        "brain":  ["neurotox", "neurologic", "cns", "seizure", "encephalopathy"],
        "lung":   ["pulmonary", "pneumonitis", "respiratory", "lung"],
    }

    for trial in trials.failed_trials:
        why = (trial.why_stopped or "").lower()
        if not why:
            continue
        for organ, keywords in toxicity_organ_keywords.items():
            if any(kw in why for kw in keywords):
                expression = _get_organ_expression(uniprot, organ)
                if expression >= EXPRESSION_SAFETY_THRESHOLD:
                    flags.append(CrossReferenceFlag(
                        type=FlagType.CORROBORATED_RISK,
                        severity=FlagSeverity.CRITICAL,
                        message=(
                            f"CRITICAL: Trial '{trial.nct_id}' failed due to {organ} toxicity "
                            f"('{trial.why_stopped}') AND target shows high {organ} expression "
                            f"({expression:.2f}). Two independent sources confirm this risk."
                        ),
                        details={
                            "trial_id": trial.nct_id,
                            "trial_title": trial.title,
                            "why_stopped": trial.why_stopped,
                            "organ": organ,
                            "expression_level": expression,
                        }
                    ))

    # -------------------------------------------------------------------
    # CHECK 4: IP crowding risk
    # Logic: many comparable drugs with active exclusivity = hard market entry
    # -------------------------------------------------------------------
    if orange_book.ip_crowding_score > 0.6:
        flags.append(CrossReferenceFlag(
            type=FlagType.IP_RISK,
            severity=FlagSeverity.MEDIUM,
            message=(
                f"High IP crowding score ({orange_book.ip_crowding_score:.2f}) "
                "in comparable drug space. Multiple active exclusivity periods may limit "
                "commercial opportunity or require design-around strategies."
            ),
            details={
                "ip_crowding_score": orange_book.ip_crowding_score,
                "comparable_drugs": len(orange_book.comparable_drugs),
            }
        ))

    # -------------------------------------------------------------------
    # CHECK 5: Data gap flag — low confidence due to missing data
    # Logic: if multiple workers failed, our confidence in any conclusion is low
    # -------------------------------------------------------------------
    from models import WorkerStatus
    failed_workers = []
    for name, result in [
        ("Open Targets", open_targets),
        ("ClinicalTrials", trials),
        ("PubMed", pubmed),
        ("UniProt", uniprot),
        ("Drugs@FDA", fda_drugs),
        ("Orange Book", orange_book),
    ]:
        if result.meta.status == WorkerStatus.FAILED:
            failed_workers.append(name)

    if len(failed_workers) >= 2:
        flags.append(CrossReferenceFlag(
            type=FlagType.DATA_GAP,
            severity=FlagSeverity.MEDIUM,
            message=(
                f"{len(failed_workers)} data source(s) failed to return data: "
                f"{', '.join(failed_workers)}. Scores and recommendations have reduced confidence."
            ),
            details={"failed_workers": failed_workers}
        ))

    # -------------------------------------------------------------------
    # CHECK 6: Strong tractability but NO clinical activity
    # Logic: target looks druggable but nobody is pursuing it → why not?
    # -------------------------------------------------------------------
    if (open_targets.tractability_score > 0.7
            and len(trials.active_trials) == 0
            and len(trials.completed_trials) == 0):
        flags.append(CrossReferenceFlag(
            type=FlagType.CONTRADICTION,
            severity=FlagSeverity.LOW,
            message=(
                f"High tractability score ({open_targets.tractability_score:.2f}) "
                "but no active or completed clinical trials found. "
                "Consider why this apparently druggable target has no clinical activity."
            ),
            details={
                "tractability_score": open_targets.tractability_score,
                "active_trials": 0,
            }
        ))

    # -------------------------------------------------------------------
    # CHECK 7a: Trial terminated due to patient harm / mortality → CRITICAL
    # Logic: any termination citing death, increased mortality, worsened patient
    #        outcomes, or unacceptable adverse events = strongest safety signal.
    #        "worsening" covers BACE1 verubecestat/EPOCH (cognitive worsening).
    # -------------------------------------------------------------------
    MORTALITY_HARM_KEYWORDS = [
        "mortality", "death", "died", "fatal", "patient deaths",
        "increased cardiovascular", "serious adverse event",
        "data safety monitoring board", "unacceptable toxicity", "excess mortality",
        "cardiovascular event", "increased risk of death",
        "worsening", "worse outcome", "deterioration", "detrimental",
        "harm to participants", "risk to participants",
        # Organ-specific toxicity endpoints (standalone — don't require UniProt corroboration)
        "hepatotoxicity", "hepatotox", "liver toxicity", "liver failure", "liver enzyme",
        "cardiotoxicity", "cardiotox", "cardiac toxicity", "qt prolongation",
        "nephrotoxicity", "nephrotox", "renal toxicity", "renal failure",
        "neurotoxicity", "neurotox", "seizure",
    ]
    for trial in trials.failed_trials:
        why = (trial.why_stopped or "").lower()
        if any(kw in why for kw in MORTALITY_HARM_KEYWORDS):
            flags.append(CrossReferenceFlag(
                type=FlagType.SAFETY_FLAG,
                severity=FlagSeverity.CRITICAL,
                message=(
                    f"CRITICAL: Trial '{trial.nct_id}' was terminated due to patient harm or "
                    f"worsened outcomes: '{trial.why_stopped}'."
                ),
                details={
                    "trial_id": trial.nct_id,
                    "trial_title": trial.title,
                    "why_stopped": trial.why_stopped,
                }
            ))

    # -------------------------------------------------------------------
    # CHECK 7b: Efficacy failure terminations → HIGH (Phase III → CRITICAL)
    # Logic: "lack of efficacy" / "futility" means the drug was tested and
    #        found not to work — the target hypothesis failed.
    #        Phase III efficacy failure is a class-killing event → CRITICAL.
    #        (Distinct from safety: the drug does nothing, not that it harms.)
    # BACE1 coverage: verubecestat EPOCH/APECS, lanabecestat, elenbecestat all
    #        stopped for futility or lack of efficacy.
    # -------------------------------------------------------------------
    EFFICACY_FAILURE_KEYWORDS = [
        "lack of efficacy", "lack efficacy",
        "futility", "pre-specified futility", "interim futility",
        "did not meet", "failed to meet", "failure to meet",
        "no significant", "insufficient efficacy", "no efficacy",
        "negative results", "negative outcome",
        "benefit-risk", "unfavorable risk", "risk-benefit",
    ]
    _flagged_by_7a = {
        f.details.get("trial_id") for f in flags
        if f.details and "trial_id" in f.details
    }
    for trial in trials.failed_trials:
        if trial.nct_id in _flagged_by_7a:
            continue
        why = (trial.why_stopped or "").lower()
        if not any(kw in why for kw in EFFICACY_FAILURE_KEYWORDS):
            continue

        # Determine phase for severity escalation
        is_phase3 = trial.phase and ("3" in trial.phase.upper() or "4" in trial.phase.upper())

        if is_phase3:
            flags.append(CrossReferenceFlag(
                type=FlagType.CONTRADICTION,
                severity=FlagSeverity.CRITICAL,
                message=(
                    f"CRITICAL: Phase III trial '{trial.nct_id}' terminated for efficacy failure: "
                    f"'{trial.why_stopped}'. Phase III failure is a class-level event — "
                    "the target hypothesis was tested at scale and rejected."
                ),
                details={
                    "trial_id": trial.nct_id,
                    "trial_title": trial.title,
                    "why_stopped": trial.why_stopped,
                    "phase": trial.phase,
                }
            ))
        else:
            flags.append(CrossReferenceFlag(
                type=FlagType.CONTRADICTION,
                severity=FlagSeverity.HIGH,
                message=(
                    f"Trial '{trial.nct_id}' (phase: {trial.phase or 'unknown'}) terminated for "
                    f"efficacy failure: '{trial.why_stopped}'. Target hypothesis not supported."
                ),
                details={
                    "trial_id": trial.nct_id,
                    "trial_title": trial.title,
                    "why_stopped": trial.why_stopped,
                    "phase": trial.phase,
                }
            ))

    # -------------------------------------------------------------------
    # CHECK 8: Multiple failed trials — potential target-class failure
    # Logic: ≥3 total failures = HIGH class-failure signal, escalated to CRITICAL
    #        if any of those failures were Phase III (biology is the problem).
    #        1-2 failures not already flagged = MEDIUM.
    # -------------------------------------------------------------------
    already_flagged_trial_ids = {
        f.details.get("trial_id") for f in flags
        if f.details and "trial_id" in f.details
    }
    unflagged_failures = [
        t for t in trials.failed_trials if t.nct_id not in already_flagged_trial_ids
    ]

    if len(trials.failed_trials) >= 3:
        # Escalate to CRITICAL if any Phase III among the failures
        has_phase3_failure = any(
            t.phase and ("3" in t.phase.upper() or "4" in t.phase.upper())
            for t in trials.failed_trials
        )
        check8_severity = FlagSeverity.CRITICAL if has_phase3_failure else FlagSeverity.HIGH
        phase3_note = " Including Phase III failure(s) — this signals a target-biology problem, not a drug-design problem." if has_phase3_failure else ""

        flags.append(CrossReferenceFlag(
            type=FlagType.CONTRADICTION,
            severity=check8_severity,
            message=(
                f"Repeated target-class failure: {len(trials.failed_trials)} trials "
                "terminated or withdrawn for this target. When multiple programs fail on "
                f"the same target, the biology is likely the problem.{phase3_note}"
            ),
            details={
                "failed_trial_count": len(trials.failed_trials),
                "has_phase3_failure": has_phase3_failure,
                "failure_reasons": [
                    t.why_stopped for t in trials.failed_trials if t.why_stopped
                ][:5],
            }
        ))
    elif unflagged_failures:
        flags.append(CrossReferenceFlag(
            type=FlagType.CONTRADICTION,
            severity=FlagSeverity.MEDIUM,
            message=(
                f"{len(trials.failed_trials)} terminated/withdrawn trial(s) found for this target. "
                f"Reason: '{trials.failed_trials[0].why_stopped or 'not specified'}'. "
                "Investigate before advancing."
            ),
            details={
                "failed_trial_count": len(trials.failed_trials),
                "failure_reasons": [
                    t.why_stopped for t in trials.failed_trials if t.why_stopped
                ][:3],
            }
        ))

    # Sort by severity: CRITICAL > HIGH > MEDIUM > LOW
    severity_order = {
        FlagSeverity.CRITICAL: 0,
        FlagSeverity.HIGH: 1,
        FlagSeverity.MEDIUM: 2,
        FlagSeverity.LOW: 3,
    }
    flags.sort(key=lambda f: severity_order[f.severity])

    return flags

"""
engine/scoring.py — Weighted Evidence Scoring Algorithm

Computes science score, regulatory score, and combined TargetIQ score.
All sub-components normalise to 0.0–1.0 before weighting.
Final scores are scaled to 0–100.
"""

import math
from typing import Optional
from models import (
    Scores, CrossReferenceFlag, FlagSeverity, FlagType,
    OpenTargetsResult, ClinicalTrialsResult, PubMedResult,
    UniProtResult, FDADrugsResult, OrangeBookResult,
    RegulatoryPathwayResult, SpecialDesignation
)
from config import (
    SCIENCE_WEIGHTS, REGULATORY_WEIGHTS,
    SCIENCE_WEIGHT, REGULATORY_WEIGHT,
    THRESHOLD_GO, THRESHOLD_MODERATE_CAUTION, THRESHOLD_CAUTION,
    SAFETY_ORGANS, EXPRESSION_SAFETY_THRESHOLD,
    PATHWAY_COMPLEXITY, DESIGNATION_SCORES,
)
# Imported here to keep confidence logic separate; lazy-safe (numpy inside)
from confidence import compute_confidence


# ---------------------------------------------------------------------------
# Phase-weighted clinical score
# ---------------------------------------------------------------------------

def _extract_phase_num(phase_str: Optional[str]) -> Optional[str]:
    """
    Extract the highest phase number from a ClinicalTrials.gov phase string.
    'PHASE3' → '3', 'PHASE1' → '1', 'EARLY_PHASE1' → '1', None → None.
    Phase 4 treated as Phase 3 (post-approval surveillance, same signal weight).
    """
    if not phase_str:
        return None
    s = phase_str.upper()
    if "4" in s or "3" in s:
        return "3"
    if "2" in s:
        return "2"
    if "1" in s:
        return "1"
    return None


# Higher phase = higher weight. Phase 3 failures are existential; Phase 1 is routine.
_PHASE_SUCCESS_WEIGHTS = {"3": 3.0, "2": 1.5, "1": 0.5}
_PHASE_DEFAULT_WEIGHT  = 1.0


def _phase_weighted_clinical_score(trials: ClinicalTrialsResult) -> float:
    """
    Phase-weighted clinical success score (0-1).

    The root problem with raw success_rate:
      - BACE1 has a dozen Phase I dose-escalation completions (expected to succeed)
        plus 4+ Phase III terminations — raw success_rate ≈ 0.6, misleadingly 'moderate'
      - Each trial gets equal weight regardless of phase

    This function weights by phase severity so Phase III failures dominate:
      completed_weight_sum / total_weight_sum

    Example: 6 Phase I completions + 3 Phase III failures
      raw rate   = 6/9 = 0.67  (looks OK)
      phase-weighted = (6×0.5) / (6×0.5 + 3×3.0) = 3.0 / 12.0 = 0.25  (correctly severe)
    """
    total_weight   = 0.0
    success_weight = 0.0

    for t in trials.completed_trials:
        w = _PHASE_SUCCESS_WEIGHTS.get(_extract_phase_num(t.phase), _PHASE_DEFAULT_WEIGHT)
        total_weight   += w
        success_weight += w

    for t in trials.failed_trials:
        w = _PHASE_SUCCESS_WEIGHTS.get(_extract_phase_num(t.phase), _PHASE_DEFAULT_WEIGHT)
        total_weight += w

    if total_weight == 0:
        return trials.success_rate  # no phase data — fall back to raw rate

    return round(success_weight / total_weight, 3)


# ---------------------------------------------------------------------------
# Sub-score components
# ---------------------------------------------------------------------------

def _safety_score(uniprot: UniProtResult, flags: list[CrossReferenceFlag]) -> float:
    """
    Safety score (0-1). Starts at 1.0, penalised by:
    - High expression in safety organs
    - Cross-reference flags (especially critical ones)
    """
    score = 1.0

    # Penalty for organ expression
    for organ in SAFETY_ORGANS:
        for te in uniprot.tissue_expression:
            if organ in te.tissue.lower():
                if te.level_numeric >= EXPRESSION_SAFETY_THRESHOLD:
                    score -= 0.15  # -15% per organ above threshold

    # Penalty for flags
    flag_penalties = {
        FlagSeverity.CRITICAL: 0.30,
        FlagSeverity.HIGH:     0.15,
        FlagSeverity.MEDIUM:   0.07,
        FlagSeverity.LOW:      0.02,
    }
    for flag in flags:
        if flag.type in (FlagType.SAFETY_FLAG, FlagType.CORROBORATED_RISK):
            score -= flag_penalties.get(flag.severity, 0.0)

    return max(0.0, min(1.0, score))


def _pathway_score(reg: RegulatoryPathwayResult) -> float:
    """Regulatory pathway complexity → higher score = simpler/faster pathway."""
    pathway = reg.recommended_pathway or "unknown"
    return PATHWAY_COMPLEXITY.get(pathway, 0.2)


def _designation_score(reg: RegulatoryPathwayResult, trials: ClinicalTrialsResult) -> float:
    """
    Score based on special designations earned (additive, capped at 1.0).

    Designation inflation fix: Alzheimer's / high-designation diseases can accumulate
    Fast Track + Breakthrough + Priority Review even when the entire target class has
    failed Phase III. Designations reflect regulatory opportunity, not scientific merit.
    Cap at 0.30 when ≥2 Phase III terminations exist — the designations are moot if
    the biology is broken.
    """
    score = 0.0
    for desig in reg.special_designations:
        score += DESIGNATION_SCORES.get(desig.value, 0.0)
    raw = min(1.0, score)

    # Count Phase III failures across all failed trials
    phase3_failures = sum(
        1 for t in trials.failed_trials
        if t.phase and ("3" in t.phase.upper() or "4" in t.phase.upper())
    )
    if phase3_failures >= 2:
        # Cap at 0.30: designations still have some regulatory value but they can't
        # offset repeated Phase III evidence that the target doesn't work.
        return min(raw, 0.30)
    return raw


def _competition_score(fda: FDADrugsResult) -> float:
    """
    Competitive landscape score (0-1). 
    More approved drugs = harder market entry = lower score.
    But some precedent (1-3 drugs) is actually good (de-risks regulatory path).
    """
    n = len(fda.approved_drugs)
    if n == 0:
        return 0.5    # No precedent: unknown territory, neutral score
    if n <= 3:
        return 0.8    # Some precedent: good, pathway is known
    if n <= 8:
        return 0.5    # Moderate competition
    return 0.2        # Very crowded market


def _precedent_score(fda: FDADrugsResult) -> float:
    """
    Regulatory precedent strength (0-1).
    Approved drugs with same MOA = strong precedent for regulatory approach.
    """
    same_moa = len(fda.approved_drugs_same_moa)
    if same_moa == 0:
        return 0.3  # No precedent — regulators will scrutinise more
    if same_moa <= 2:
        return 0.7  # Good precedent
    return 1.0      # Strong precedent


def _ip_score(orange_book: OrangeBookResult) -> float:
    """IP freedom to operate score (0-1). Lower crowding = higher score."""
    return 1.0 - orange_book.ip_crowding_score


def _weighted_average(components: dict[str, tuple[float, float]]) -> float:
    """
    Compute weighted average from {name: (value_0_to_1, weight)} dict.
    Normalises weights in case they don't sum to 1.0.
    Returns 0-1.
    """
    total_weight = sum(w for _, w in components.values())
    if total_weight == 0:
        return 0.0
    return sum(v * w for v, w in components.values()) / total_weight


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_scores_full(
    open_targets: OpenTargetsResult,
    trials: ClinicalTrialsResult,
    pubmed: PubMedResult,
    uniprot: UniProtResult,
    fda_data: FDADrugsResult,
    orange_book: OrangeBookResult,
    reg: RegulatoryPathwayResult,
    flags: list[CrossReferenceFlag],
) -> Scores:
    """Full version of compute_scores with orange_book properly included."""

    safety = _safety_score(uniprot, flags)

    science_components = {
        "genetic_evidence":  (open_targets.genetic_score,      SCIENCE_WEIGHTS["genetic_evidence"]),
        "literature_support": (pubmed.relevance_score,          SCIENCE_WEIGHTS["literature_support"]),
        "prior_clinical":    (_phase_weighted_clinical_score(trials), SCIENCE_WEIGHTS["prior_clinical"]),
        "tractability":      (open_targets.tractability_score,  SCIENCE_WEIGHTS["tractability"]),
        "safety_profile":    (safety,                           SCIENCE_WEIGHTS["safety_profile"]),
    }
    science_raw = _weighted_average(science_components)
    science_score = round(science_raw * 100, 1)

    reg_components = {
        "pathway_complexity":    (_pathway_score(reg),          REGULATORY_WEIGHTS["pathway_complexity"]),
        "special_designations":  (_designation_score(reg, trials), REGULATORY_WEIGHTS["special_designations"]),
        "competitive_landscape": (_competition_score(fda_data), REGULATORY_WEIGHTS["competitive_landscape"]),
        "precedent_strength":    (_precedent_score(fda_data),   REGULATORY_WEIGHTS["precedent_strength"]),
        "ip_freedom":            (_ip_score(orange_book),       REGULATORY_WEIGHTS["ip_freedom"]),
    }
    reg_raw = _weighted_average(reg_components)
    reg_score = round(reg_raw * 100, 1)

    combined = round((science_score * SCIENCE_WEIGHT) + (reg_score * REGULATORY_WEIGHT), 1)

    # Apply direct combined-score penalties for HIGH and CRITICAL flags.
    # Safety sub-score only penalises the science component; these penalties
    # ensure severe flags drive the final recommendation regardless of other signals.
    for flag in flags:
        if flag.severity == FlagSeverity.CRITICAL:
            combined -= 15.0  # -15 pts per critical flag
        elif flag.severity == FlagSeverity.HIGH:
            combined -= 7.0   # -7 pts per high flag
        elif flag.severity == FlagSeverity.MEDIUM:
            combined -= 4.0   # -4 pts per medium flag
    combined = round(max(0.0, combined), 1)

    if combined >= THRESHOLD_GO:
        recommendation = "GO"
    elif combined >= THRESHOLD_MODERATE_CAUTION:
        recommendation = "MODERATE CAUTION"
    elif combined >= THRESHOLD_CAUTION:
        recommendation = "CAUTION"
    else:
        recommendation = "NO-GO"

    # Confidence metrics: bootstrap CI on trial success rate + MC score stability.
    # These are informational — a failure here never blocks the main result.
    confidence = None
    try:
        confidence = compute_confidence(
            genetic_score=open_targets.genetic_score,
            tractability_score=open_targets.tractability_score,
            success_rate=trials.success_rate,
            relevance_score=pubmed.relevance_score,
            safety_score=safety,
            regulatory_score_100=reg_score,
            flags=flags,
            completed_trials=len(trials.completed_trials),
            failed_trials=len(trials.failed_trials),
            base_recommendation=recommendation,
        )
    except Exception:
        pass  # numpy unavailable or unexpected error — degrade gracefully

    return Scores(
        science_score=science_score,
        regulatory_score=reg_score,
        combined_score=combined,
        recommendation=recommendation,
        confidence=confidence,
    )

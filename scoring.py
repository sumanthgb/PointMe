"""
engine/scoring.py — Weighted Evidence Scoring Algorithm

Computes science score, regulatory score, and combined TargetIQ score.
All sub-components normalise to 0.0–1.0 before weighting.
Final scores are scaled to 0–100.
"""

import math
from models import (
    Scores, CrossReferenceFlag, FlagSeverity, FlagType,
    OpenTargetsResult, ClinicalTrialsResult, PubMedResult,
    UniProtResult, FDADrugsResult, OrangeBookResult,
    RegulatoryPathwayResult, SpecialDesignation
)
from config import (
    SCIENCE_WEIGHTS, REGULATORY_WEIGHTS,
    SCIENCE_WEIGHT, REGULATORY_WEIGHT,
    THRESHOLD_GO, THRESHOLD_CAUTION,
    SAFETY_ORGANS, EXPRESSION_SAFETY_THRESHOLD,
    PATHWAY_COMPLEXITY, DESIGNATION_SCORES,
)


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


def _designation_score(reg: RegulatoryPathwayResult) -> float:
    """Score based on special designations earned (additive, capped at 1.0)."""
    score = 0.0
    for desig in reg.special_designations:
        score += DESIGNATION_SCORES.get(desig.value, 0.0)
    return min(1.0, score)


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
        "prior_clinical":    (trials.success_rate,              SCIENCE_WEIGHTS["prior_clinical"]),
        "tractability":      (open_targets.tractability_score,  SCIENCE_WEIGHTS["tractability"]),
        "safety_profile":    (safety,                           SCIENCE_WEIGHTS["safety_profile"]),
    }
    science_raw = _weighted_average(science_components)
    science_score = round(science_raw * 100, 1)

    reg_components = {
        "pathway_complexity":    (_pathway_score(reg),          REGULATORY_WEIGHTS["pathway_complexity"]),
        "special_designations":  (_designation_score(reg),      REGULATORY_WEIGHTS["special_designations"]),
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
    elif combined >= THRESHOLD_CAUTION:
        recommendation = "CAUTION"
    else:
        recommendation = "NO-GO"

    return Scores(
        science_score=science_score,
        regulatory_score=reg_score,
        combined_score=combined,
        recommendation=recommendation,
    )

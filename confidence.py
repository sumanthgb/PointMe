"""
confidence.py — Bootstrap CI + Monte Carlo score stability

Two complementary techniques run AFTER scoring, adding ~20ms of CPU time.

WHY THIS EXISTS:
  The scoring engine produces a single point estimate for each component.
  A 20% trial success rate from N=10 is a very different claim than 20% from
  N=200. A genetic score of 0.72 might mean the recommendation flips to GO
  under slightly different data, or it might be rock-solid. Neither fact is
  visible in the point estimate. These techniques make the uncertainty explicit.

TECHNIQUE 1 — Bootstrap CI on trial success_rate:
  The success_rate is completed / (completed + failed). With small N (common:
  3–15 trials per target), this is a very noisy estimate. The bootstrap
  resamples the observed trial outcomes with replacement and computes the success
  rate for each resample. The 2.5th–97.5th percentile range is the 95% CI.
  Example: 2 completed, 8 failed → rate = 20%, CI = [2%, 48%].
  No distributional assumptions — just the data.

TECHNIQUE 2 — Monte Carlo score stability:
  Perturbs the 5 science inputs by calibrated Gaussian noise (see SCIENCE_NOISE),
  recomputes the combined score 5000 times, and reports:
  - 95% CI on combined score
  - Recommendation stability: fraction of iterations that agree with the
    deterministic recommendation. A value of 0.82 means "18% of plausible
    data perturbations flip this recommendation" — meaningful for borderline cases.

  The regulatory score is held FIXED because it comes from a deterministic
  rules engine (pathway, designations, precedent) — there is no stochastic
  component to simulate.

  Flag penalties are also held fixed — they are hard, rule-based signals.
"""

import numpy as np

from models import ScoreConfidence, CrossReferenceFlag, FlagSeverity
from config import (
    SCIENCE_WEIGHTS, SCIENCE_WEIGHT, REGULATORY_WEIGHT,
    THRESHOLD_GO, THRESHOLD_CAUTION,
)


# ---------------------------------------------------------------------------
# Noise model for Monte Carlo science inputs
# ---------------------------------------------------------------------------
# Each σ is the estimated standard deviation of measurement error for that source.
#
# genetic_evidence (σ=0.05):
#   Open Targets uses a Bayesian multi-evidence aggregation model that produces
#   relatively stable scores. Small σ is appropriate.
#
# literature_support (σ=0.05):
#   PubMed volume + recency is deterministic given the query. σ captures
#   query sensitivity (slightly different search terms → slightly different count).
#
# prior_clinical (σ=0.10):
#   Trial N is almost always small. σ=0.10 reflects this; the bootstrap CI
#   gives the full picture separately (see bootstrap_success_rate_ci).
#
# tractability (σ=0.10):
#   Computed from a discrete label → numeric mapping. The label boundary
#   between e.g. "Predicted Tractable High Confidence" and "Advanced Clinical"
#   represents roughly ±1 tier of uncertainty → σ=0.10.
#
# safety_profile (σ=0.05):
#   Derived from binary threshold crossings on tissue expression. Stable.

SCIENCE_NOISE: dict[str, float] = {
    "genetic_evidence":   0.05,
    "literature_support": 0.05,
    "prior_clinical":     0.10,
    "tractability":       0.10,
    "safety_profile":     0.05,
}

# Order must match how scoring.py iterates the science_components dict.
# Python 3.7+ dicts preserve insertion order; this matches SCIENCE_WEIGHTS in config.py.
_SCIENCE_KEY_ORDER = [
    "genetic_evidence",
    "literature_support",
    "prior_clinical",
    "tractability",
    "safety_profile",
]


# ---------------------------------------------------------------------------
# Helper: reproduce flag penalties (mirrors scoring.py, must stay in sync)
# ---------------------------------------------------------------------------

def _total_flag_penalty(flags: list[CrossReferenceFlag]) -> float:
    """Sum of all flag penalties applied to the combined score."""
    penalty = 0.0
    for flag in flags:
        if flag.severity == FlagSeverity.CRITICAL:
            penalty += 15.0
        elif flag.severity == FlagSeverity.HIGH:
            penalty += 7.0
        elif flag.severity == FlagSeverity.MEDIUM:
            penalty += 4.0
    return penalty


# ---------------------------------------------------------------------------
# Technique 1: Bootstrap CI on trial success rate
# ---------------------------------------------------------------------------

def bootstrap_success_rate_ci(
    completed: int,
    failed: int,
    n_iterations: int = 2000,
) -> tuple[float, float]:
    """
    Non-parametric 95% bootstrap confidence interval on trial success_rate.

    Args:
        completed:     Count of COMPLETED trials.
        failed:        Count of TERMINATED / WITHDRAWN / SUSPENDED trials.
        n_iterations:  Bootstrap resamples (2000 is sufficient; < 5ms at N=20).

    Returns:
        (ci_low, ci_high) as 0-1 fractions (not percentages).
        Returns (0.0, 0.0) if no resolved trials.
    """
    total = completed + failed
    if total == 0:
        return (0.0, 0.0)

    outcomes = np.array([1] * completed + [0] * failed)
    # Draw n_iterations bootstrap samples of size `total`, compute mean each time.
    # np.random.choice with a 2D size argument is ~10x faster than a Python loop.
    samples = np.random.choice(outcomes, size=(n_iterations, total), replace=True)
    rates = samples.mean(axis=1)

    return (float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5)))


# ---------------------------------------------------------------------------
# Technique 2: Monte Carlo score stability
# ---------------------------------------------------------------------------

def compute_confidence(
    genetic_score: float,
    tractability_score: float,
    success_rate: float,
    relevance_score: float,
    safety_score: float,
    regulatory_score_100: float,
    flags: list[CrossReferenceFlag],
    completed_trials: int,
    failed_trials: int,
    base_recommendation: str,
    n_mc: int = 5000,
) -> ScoreConfidence:
    """
    Compute bootstrap CI + Monte Carlo confidence metrics for a scoring result.

    Args:
        genetic_score:         0-1, from Open Targets
        tractability_score:    0-1, from Open Targets
        success_rate:          0-1, from ClinicalTrials
        relevance_score:       0-1, from PubMed
        safety_score:          0-1, from _safety_score() in scoring.py
        regulatory_score_100:  0-100, from deterministic rules engine (held fixed)
        flags:                 CrossReferenceFlag list (for flag penalties)
        completed_trials:      count, used for bootstrap
        failed_trials:         count, used for bootstrap
        base_recommendation:   "GO" | "CAUTION" | "NO-GO" (the deterministic result)
        n_mc:                  Monte Carlo iterations (5000 → ~15ms on a CPU core)

    Returns:
        ScoreConfidence with all CI and stability fields populated.
    """
    # --- Bootstrap CI on success rate ---
    sr_ci_low, sr_ci_high = bootstrap_success_rate_ci(completed_trials, failed_trials)

    # --- Monte Carlo: perturb science inputs ---
    # Point estimates in the same order as _SCIENCE_KEY_ORDER
    means = np.array([
        genetic_score,      # genetic_evidence
        relevance_score,    # literature_support
        success_rate,       # prior_clinical
        tractability_score, # tractability
        safety_score,       # safety_profile
    ])
    sigmas  = np.array([SCIENCE_NOISE[k] for k in _SCIENCE_KEY_ORDER])
    weights = np.array([SCIENCE_WEIGHTS[k] for k in _SCIENCE_KEY_ORDER])

    # Draw n_mc samples, each with all 5 inputs perturbed simultaneously.
    # shape: (n_mc, 5), clipped to valid [0, 1] range.
    samples = np.clip(
        np.random.normal(loc=means, scale=sigmas, size=(n_mc, 5)),
        0.0, 1.0,
    )

    # Weighted average science score (0-1) → scale to 0-100
    weight_sum   = weights.sum()
    science_raw  = (samples * weights).sum(axis=1) / weight_sum   # (n_mc,)
    science_100  = science_raw * 100.0

    # Combined score (regulatory held fixed, flags held fixed)
    penalty  = _total_flag_penalty(flags)
    combined = np.clip(
        (science_100 * SCIENCE_WEIGHT) + (regulatory_score_100 * REGULATORY_WEIGHT) - penalty,
        0.0, 100.0,
    )

    # 95% CI on combined score
    ci_low  = float(np.percentile(combined, 2.5))
    ci_high = float(np.percentile(combined, 97.5))

    # Recommendation stability: fraction of MC iterations matching the deterministic result.
    # np.where with three args returns an array of strings — no loop needed.
    mc_recs   = np.where(combined >= THRESHOLD_GO, "GO",
                np.where(combined >= THRESHOLD_CAUTION, "CAUTION", "NO-GO"))
    stability = float((mc_recs == base_recommendation).mean())

    return ScoreConfidence(
        recommendation_stability=round(stability, 3),
        combined_score_ci_low=round(ci_low, 1),
        combined_score_ci_high=round(ci_high, 1),
        success_rate_ci_low=round(sr_ci_low, 3),
        success_rate_ci_high=round(sr_ci_high, 3),
        n_trials_observed=completed_trials + failed_trials,
    )

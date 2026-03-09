"""
cost_model.py — Drug Development Cost & Timeline Estimation

Architecture adapted from compl_ai/systems/roadmap_generator.py:
  that project built a DAG-based testing roadmap for medical devices with
  per-test (cost_low, cost_high, weeks_low, weeks_high) bounds and triangular
  MC sampling for critical-path analysis.

This module applies the same pattern at drug-development scale:
  - PHASE_LIBRARY replaces MASTER_TEST_LIBRARY — phases instead of test nodes
  - Same (cost_low, cost_high, years_low, years_high) per-entry format
  - Drug phases are sequential (no DAG parallelization needed) — timeline is a sum
  - Designation modifiers compress the timeline (analogous to waiver logic in compl_ai)
  - Failure-rate multiplier inflates clinical-phase cost (no analog in compl_ai)
  - MC uses triangular distributions, same as compl_ai

COST FIGURES:
  All costs are out-of-pocket (not capitalized) in 2024 USD for a single
  indication of a single molecule. Capitalized portfolio costs (which include
  cost of capital and the cost of failures across all programs) are typically
  3–5× higher — the LLM synthesis layer should surface this caveat.

  Sources: DiMasi et al. 2016 (JAMA), Tufts CSDD reports, FDA PDUFA data,
           PhRMA 2023 profile reports, Deloitte Insights pharma R&D surveys.
"""

from __future__ import annotations

from models import (
    DevelopmentCostEstimate, DevelopmentPhase,
    RegulatoryPathwayResult, ClinicalTrialsResult, CrossReferenceFlag,
)


# ---------------------------------------------------------------------------
# Phase library — drug development phases by regulatory pathway
# ---------------------------------------------------------------------------

PHASE_LIBRARY: dict[str, list[dict]] = {

    # -----------------------------------------------------------------------
    # 505(b)(1) — Full standalone NDA, novel small-molecule entity
    # No reliance on existing drug approvals. Most expensive, longest pathway.
    # -----------------------------------------------------------------------
    "505(b)(1)": [
        {
            "name": "Preclinical & IND-Enabling Studies",
            "cost_low":  15_000_000,
            "cost_high": 60_000_000,
            "years_low": 2.0,
            "years_high": 4.0,
            "notes": (
                "Lead optimization, safety pharmacology, 28/90-day toxicology, "
                "reproductive toxicology, ADME/PK studies, formulation. IND submission."
            ),
        },
        {
            "name": "Phase I Clinical Trial",
            "cost_low":  10_000_000,
            "cost_high": 30_000_000,
            "years_low": 1.0,
            "years_high": 2.0,
            "notes": (
                "First-in-human, dose escalation, safety/PK/PD. "
                "~50–100 healthy volunteers or patients."
            ),
        },
        {
            "name": "Phase II Clinical Trial",
            "cost_low":  35_000_000,
            "cost_high": 120_000_000,
            "years_low": 2.0,
            "years_high": 4.0,
            "notes": (
                "Proof of concept, dose selection. ~100–500 patients. "
                "Highest attrition rate of any phase (~60% failure)."
            ),
        },
        {
            "name": "Phase III Clinical Trial",
            "cost_low":  120_000_000,
            "cost_high": 500_000_000,
            "years_low": 3.0,
            "years_high": 7.0,
            "notes": (
                "Pivotal efficacy/safety, ~500–3000+ patients, often global multi-site. "
                "A single large Phase III can exceed $300M."
            ),
        },
        {
            "name": "NDA Submission & FDA Review",
            "cost_low":   5_000_000,
            "cost_high":  20_000_000,
            "years_low":  1.0,
            "years_high": 2.0,
            "notes": (
                "Dossier compilation, advisory committee, PDUFA review clock: "
                "12 months (standard) or 6 months (Priority Review)."
            ),
        },
    ],

    # -----------------------------------------------------------------------
    # 505(b)(2) — Abbreviated NDA relying on existing FDA drug approval data
    # Suitable when an approved drug's safety/efficacy supports the new indication
    # or formulation. Significantly cheaper than full 505(b)(1).
    # -----------------------------------------------------------------------
    "505(b)(2)": [
        {
            "name": "Bridging Studies & Preclinical",
            "cost_low":   5_000_000,
            "cost_high":  25_000_000,
            "years_low":  1.0,
            "years_high": 2.0,
            "notes": (
                "Bioavailability/bioequivalence studies; safety bridging where needed. "
                "Relies on FDA's prior findings for the Reference Listed Drug (RLD)."
            ),
        },
        {
            "name": "Phase II/III Clinical Trial",
            "cost_low":  25_000_000,
            "cost_high": 100_000_000,
            "years_low": 2.0,
            "years_high": 4.0,
            "notes": (
                "Streamlined clinical program — scope depends on extent of reliance "
                "on the RLD. May not require full Phase III if bridging is sufficient."
            ),
        },
        {
            "name": "NDA Submission & FDA Review",
            "cost_low":  3_000_000,
            "cost_high": 10_000_000,
            "years_low": 0.5,
            "years_high": 1.0,
            "notes": "Simpler dossier than 505(b)(1) — existing safety data reduces CMC scope.",
        },
    ],

    # -----------------------------------------------------------------------
    # BLA — Biologics License Application (antibodies, cell therapies, etc.)
    # Higher per-phase cost due to manufacturing complexity and larger trials.
    # -----------------------------------------------------------------------
    "BLA": [
        {
            "name": "Preclinical, CMC & IND-Enabling Studies",
            "cost_low":  25_000_000,
            "cost_high": 120_000_000,
            "years_low": 2.0,
            "years_high": 5.0,
            "notes": (
                "Expression system development, manufacturing scale-up, full CMC package. "
                "Biologics manufacturing is 5–10× more capital-intensive than small molecules."
            ),
        },
        {
            "name": "Phase I Clinical Trial",
            "cost_low":  15_000_000,
            "cost_high": 60_000_000,
            "years_low": 1.0,
            "years_high": 3.0,
            "notes": (
                "First-in-human for biologic; safety, PK, immunogenicity monitoring. "
                "Typically longer than small-molecule Phase I due to PK profile complexity."
            ),
        },
        {
            "name": "Phase II Clinical Trial",
            "cost_low":  50_000_000,
            "cost_high": 200_000_000,
            "years_low": 2.0,
            "years_high": 5.0,
            "notes": "Proof of concept. Per-patient costs are higher than small-molecule trials.",
        },
        {
            "name": "Phase III Clinical Trial",
            "cost_low":  200_000_000,
            "cost_high": 1_000_000_000,
            "years_low": 3.0,
            "years_high": 8.0,
            "notes": (
                "Pivotal biologic trial. Global logistics, complex supply chain, "
                "high per-patient costs. A single large biologic Phase III can exceed $500M."
            ),
        },
        {
            "name": "BLA Submission & FDA Review",
            "cost_low":  10_000_000,
            "cost_high": 35_000_000,
            "years_low": 1.0,
            "years_high": 2.0,
            "notes": "BLA CMC section is more extensive than NDA. PDUFA review clock applies.",
        },
    ],
}

# Fallback if pathway is unknown or not in library
_FALLBACK_PATHWAY = "505(b)(1)"


# ---------------------------------------------------------------------------
# Designation timeline modifiers
# ---------------------------------------------------------------------------
# Applied to the TOTAL development timeline — not per-phase, not to cost.
# Rationale: special designations reduce time-to-approval via rolling review,
# intensive FDA guidance, or surrogate-endpoint approval, but they don't reduce
# the inherent cost of running a clinical trial.
#
# Only the MOST FAVORABLE (lowest) modifier is applied — designations overlap
# mechanistically, so stacking them multiplicatively would overstate the effect.
# Floor of 0.60: even in the best case, drug development takes substantial time.
#
# Sources: FDA CDER data, Tufts CSDD analyses on time-to-approval by designation.

DESIGNATION_TIMELINE_MODIFIERS: dict[str, float] = {
    "breakthrough_therapy": 0.70,  # ~30% reduction — rolling review + intensive FDA guidance
    "fast_track":           0.85,  # ~15% reduction — rolling review during late-stage
    "accelerated_approval": 0.75,  # ~25% reduction — surrogate endpoint enables Phase II approval
    "priority_review":      0.92,  # Review clock 12 mo → 6 mo; mainly submission phase
    "orphan_drug":          1.00,  # Economic incentives only, no timeline benefit
}

_MIN_TIMELINE_FACTOR = 0.60   # Minimum compression, regardless of designations stacking


# ---------------------------------------------------------------------------
# Failure-rate cost adjustment
# ---------------------------------------------------------------------------
# A low historical success_rate signals structural biology or development risk.
# This increases the expected cost of Phase II/III: more rescue arms, protocol
# amendments, additional patient populations, or the need for an additional study.
#
# Applied ONLY to phases with "clinical" in their name (not preclinical or review).

def _failure_cost_factor(success_rate: float) -> float:
    """Additional cost multiplier for clinical phases based on historical trial success rate."""
    if success_rate >= 0.60:
        return 1.00   # Healthy — no adjustment
    if success_rate >= 0.40:
        return 1.10   # Slight elevation
    if success_rate >= 0.20:
        return 1.25   # Meaningful — high attrition signals biology or design problems
    return 1.40       # Severe — repeated failures indicate significant development risk


_CLINICAL_PHASE_KEYWORDS = ("phase i", "phase ii", "phase iii", "clinical")


# ---------------------------------------------------------------------------
# Monte Carlo sampling
# ---------------------------------------------------------------------------

def _triangular_samples(low: float, high: float, n: int):
    """
    Triangular distribution with mode at the midpoint.
    Preferred over uniform because it concentrates probability around the
    'most likely' value while preserving tail exposure to the full range.
    Same choice made in compl_ai's roadmap_generator.py MC sampling.
    """
    import numpy as np
    mid = (low + high) / 2.0
    return np.random.triangular(low, mid, high, size=n)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def estimate_development_cost(
    reg: RegulatoryPathwayResult,
    trials: ClinicalTrialsResult,
    flags: list[CrossReferenceFlag],
    n_mc: int = 10_000,
) -> DevelopmentCostEstimate:
    """
    Generate a phase-by-phase drug development cost and timeline estimate.

    Steps (mirroring compl_ai roadmap_generator pipeline):
      1. Select phase library by regulatory pathway
      2. Compute timeline modifier from special designations
      3. Compute failure-rate cost multiplier from trial success_rate
      4. Build adjusted DevelopmentPhase list
      5. Monte Carlo triangular sampling → P10/P50/P90

    Args:
        reg:    RegulatoryPathwayResult (pathway + special designations)
        trials: ClinicalTrialsResult (success_rate for failure-rate modifier)
        flags:  CrossReferenceFlag list (reserved for future flag-based penalties)
        n_mc:   Monte Carlo iterations (10,000 → ~15ms on CPU)

    Returns:
        DevelopmentCostEstimate with phase breakdown, adjusted totals, and MC percentiles.
    """
    import numpy as np

    pathway    = reg.recommended_pathway or _FALLBACK_PATHWAY
    phases_raw = PHASE_LIBRARY.get(pathway, PHASE_LIBRARY[_FALLBACK_PATHWAY])

    # --- Timeline modifier: take the most favorable designation, apply floor ---
    desig_values = [d.value for d in reg.special_designations]
    timeline_factor = min(
        (DESIGNATION_TIMELINE_MODIFIERS.get(d, 1.0) for d in desig_values),
        default=1.0,
    )
    timeline_factor = max(timeline_factor, _MIN_TIMELINE_FACTOR)

    # --- Failure-rate cost multiplier for clinical phases ---
    fail_factor = _failure_cost_factor(trials.success_rate)

    # --- Build adjusted DevelopmentPhase objects ---
    phases: list[DevelopmentPhase] = []
    for p in phases_raw:
        is_clinical = any(kw in p["name"].lower() for kw in _CLINICAL_PHASE_KEYWORDS)
        cost_multiplier = fail_factor if is_clinical else 1.0

        phases.append(DevelopmentPhase(
            name=p["name"],
            cost_low_usd=int(p["cost_low"]  * cost_multiplier),
            cost_high_usd=int(p["cost_high"] * cost_multiplier),
            years_low=round(p["years_low"]  * timeline_factor, 1),
            years_high=round(p["years_high"] * timeline_factor, 1),
            notes=p.get("notes"),
        ))

    # --- Point estimate totals ---
    total_cost_low   = sum(p.cost_low_usd  for p in phases)
    total_cost_high  = sum(p.cost_high_usd for p in phases)
    total_years_low  = round(sum(p.years_low  for p in phases), 1)
    total_years_high = round(sum(p.years_high for p in phases), 1)

    # --- Monte Carlo: triangular sampling per phase, sum across phases ---
    n_phases     = len(phases)
    cost_samples = np.column_stack([
        _triangular_samples(p.cost_low_usd, p.cost_high_usd, n_mc) for p in phases
    ])   # shape: (n_mc, n_phases)
    years_samples = np.column_stack([
        _triangular_samples(p.years_low, p.years_high, n_mc) for p in phases
    ])

    total_cost_mc  = cost_samples.sum(axis=1)
    total_years_mc = years_samples.sum(axis=1)

    cost_p10  = int(np.percentile(total_cost_mc,  10))
    cost_p50  = int(np.percentile(total_cost_mc,  50))
    cost_p90  = int(np.percentile(total_cost_mc,  90))
    years_p10 = round(float(np.percentile(total_years_mc, 10)), 1)
    years_p50 = round(float(np.percentile(total_years_mc, 50)), 1)
    years_p90 = round(float(np.percentile(total_years_mc, 90)), 1)

    # --- Plain-English summary ---
    designations_applied = [
        d for d in desig_values if DESIGNATION_TIMELINE_MODIFIERS.get(d, 1.0) < 1.0
    ]

    def _fmt_usd(n: int) -> str:
        return f"${n / 1_000_000_000:.1f}B" if n >= 1_000_000_000 else f"${n / 1_000_000:.0f}M"

    desig_note = ""
    if designations_applied:
        compressed_pct = round((1 - timeline_factor) * 100)
        desig_names    = ", ".join(d.replace("_", " ").title() for d in designations_applied)
        desig_note     = f" {desig_names} designation(s) applied a {compressed_pct}% timeline compression."

    failure_note = ""
    if fail_factor > 1.0:
        failure_note = (
            f" Historical failure rate for this target class increases expected "
            f"clinical spending by ~{round((fail_factor - 1) * 100)}%."
        )

    summary = (
        f"{pathway} pathway. "
        f"Estimated out-of-pocket development cost: {_fmt_usd(total_cost_low)}–{_fmt_usd(total_cost_high)} "
        f"(P50: {_fmt_usd(cost_p50)}) over "
        f"{total_years_low}–{total_years_high} years "
        f"(P50: {years_p50} years)."
        f"{desig_note}{failure_note}"
        " Note: these are out-of-pocket estimates; capitalized costs (including cost of capital "
        "and failures across the portfolio) are typically 3–5× higher."
    )

    return DevelopmentCostEstimate(
        pathway=pathway,
        phases=phases,
        total_cost_low_usd=total_cost_low,
        total_cost_high_usd=total_cost_high,
        total_years_low=total_years_low,
        total_years_high=total_years_high,
        cost_p10_usd=cost_p10,
        cost_p50_usd=cost_p50,
        cost_p90_usd=cost_p90,
        years_p10=years_p10,
        years_p50=years_p50,
        years_p90=years_p90,
        designations_applied=designations_applied,
        summary=summary,
    )

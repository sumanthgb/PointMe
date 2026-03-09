"""
llm_synthesis.py — LLM Synthesis Layer

This is the LAST step in the pipeline. By the time we get here:
  - All 6 workers have run
  - Regulatory rules engine has fired
  - Cross-reference engine has found contradictions/flags
  - Scoring algorithm has produced a GO/CAUTION/NO-GO

The LLM's only job is to EXPLAIN what the structured data already says.
It does not make decisions. It does not invent data.
"""

# anthropic imported lazily inside function
from models import TargetIQResponse


SYNTHESIS_SYSTEM_PROMPT = """You are a senior biotech analyst writing an internal assessment memo.
You will be given a structured evidence package for a drug target-disease pair.

CRITICAL RULES:
1. Do NOT invent any data. Every claim must reference the provided payload.
2. Do NOT override the GO/CAUTION/NO-GO recommendation — it is computed by the rules engine.
3. Be precise about uncertainty: if a data source failed, acknowledge the gap.
4. Write for a sophisticated audience (biotech founders, VCs, regulatory strategists).
5. Be concise — executives read the executive summary; scientists read the rest.
"""

SYNTHESIS_USER_TEMPLATE = """
Write an assessment report for the following drug target evaluation.

TARGET: {target}
DISEASE: {disease}

SCORES:
- Science Score: {science_score}/100
- Regulatory Score: {regulatory_score}/100
- Combined TargetIQ Score: {combined_score}/100
- Recommendation: {recommendation}

SCIENTIFIC EVIDENCE:
{science_evidence}

REGULATORY ASSESSMENT:
- Recommended Pathway: {pathway}
- Special Designations: {designations}
- Estimated Timeline: {timeline}
- Estimated Cost: {cost}
- Rule Triggers (audit trail): {reasoning}

DEVELOPMENT COST & TIMELINE MODEL:
{cost_estimate}

PATENT LANDSCAPE:
{patent_radar}

CROSS-REFERENCE FLAGS ({flag_count} total):
{flags}

DATA SOURCE STATUS:
{data_sources}

Structure your response EXACTLY as follows:
1. EXECUTIVE SUMMARY (2-3 sentences: state the recommendation and top reason)
2. SCIENTIFIC EVIDENCE ASSESSMENT (genetic evidence, clinical trial landscape, literature)
3. REGULATORY PATHWAY ANALYSIS (recommended pathway, why, special designations, timeline)
4. DEVELOPMENT COST & TIMELINE (out-of-pocket estimate ranges, MC P50, key phases)
5. IP LANDSCAPE (patent density, key risks, recommended action)
6. CRITICAL RISK FLAGS (list and explain each flag, starting with most severe)
7. CONFIDENCE NOTE (note any data gaps or failed sources that limit confidence)
"""


def _format_flags(flags: list) -> str:
    if not flags:
        return "No flags detected."
    lines = []
    for f in flags:
        severity = f.severity.value if hasattr(f.severity, 'value') else f.severity
        ftype = f.type.value if hasattr(f.type, 'value') else f.type
        lines.append(f"  [{str(severity).upper()}] {ftype}: {f.message}")
    return "\n".join(lines)


def _format_data_sources(data_sources: dict) -> str:
    lines = []
    for source, info in data_sources.items():
        status = info.get("status", "unknown")
        ms = info.get("query_time_ms", 0)
        lines.append(f"  {source}: {status} ({ms}ms)")
    return "\n".join(lines) if lines else "No source metadata available."


def synthesize_with_llm(response: TargetIQResponse) -> str:
    """
    Send the fully structured TargetIQ payload to Claude for natural language synthesis.

    Args:
        response: Completed TargetIQResponse with all fields populated

    Returns:
        LLM-generated assessment report string
    """
    import anthropic
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY from environment

    reg = response.regulatory_assessment
    scores = response.scores

    # Format cost estimate section
    cost_estimate_text = "Not available."
    if response.cost_estimate:
        ce = response.cost_estimate
        cost_estimate_text = (
            f"Pathway: {ce.pathway} | "
            f"Range: ${ce.total_cost_low_usd // 1_000_000}M–${ce.total_cost_high_usd // 1_000_000}M | "
            f"P50: ${ce.cost_p50_usd // 1_000_000}M | "
            f"Timeline: {ce.total_years_low}–{ce.total_years_high} years (P50: {ce.years_p50} yrs)\n"
            f"Phase breakdown: " + ", ".join(
                f"{p.name} (${p.cost_low_usd // 1_000_000}M–${p.cost_high_usd // 1_000_000}M, "
                f"{p.years_low}–{p.years_high} yrs)"
                for p in ce.phases
            )
        )

    # Format patent radar section
    patent_radar_text = "Not available."
    if response.patent_radar:
        pr = response.patent_radar
        patent_radar_text = (
            f"{len(pr.patents)} patents analyzed | "
            f"High-risk (red): {pr.red_count} | Moderate (yellow): {pr.yellow_count}\n"
            f"Summary: {pr.summary}"
        )

    prompt = SYNTHESIS_USER_TEMPLATE.format(
        target=response.target,
        disease=response.disease,
        science_score=scores.science_score,
        regulatory_score=scores.regulatory_score,
        combined_score=scores.combined_score,
        recommendation=scores.recommendation,
        science_evidence=str(response.scientific_evidence)[:3000],  # truncate for context
        pathway=reg.recommended_pathway or "Unknown",
        designations=", ".join(d.value for d in reg.special_designations) or "None",
        timeline=reg.estimated_timeline_years or "Unknown",
        cost=reg.estimated_cost_range or "Unknown",
        reasoning="\n".join(f"  - {r}" for r in reg.reasoning),
        cost_estimate=cost_estimate_text,
        patent_radar=patent_radar_text,
        flag_count=len(response.flags),
        flags=_format_flags(response.flags),
        data_sources=_format_data_sources(response.data_sources),
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


def synthesize_with_openai_fallback(response: TargetIQResponse) -> str:
    """
    OpenAI fallback if Claude API is unavailable.
    Uses identical prompt structure.
    """
    try:
        import openai
        client = openai.OpenAI()

        reg = response.regulatory_assessment
        scores = response.scores

        cost_estimate_text = "Not available."
        if response.cost_estimate:
            ce = response.cost_estimate
            cost_estimate_text = (
                f"Pathway: {ce.pathway} | "
                f"Range: ${ce.total_cost_low_usd // 1_000_000}M–${ce.total_cost_high_usd // 1_000_000}M | "
                f"P50: ${ce.cost_p50_usd // 1_000_000}M | "
                f"Timeline: {ce.total_years_low}–{ce.total_years_high} years (P50: {ce.years_p50} yrs)"
            )
        patent_radar_text = "Not available."
        if response.patent_radar:
            pr = response.patent_radar
            patent_radar_text = (
                f"{len(pr.patents)} patents | Red: {pr.red_count} | Yellow: {pr.yellow_count}\n"
                f"Summary: {pr.summary}"
            )

        prompt = SYNTHESIS_USER_TEMPLATE.format(
            target=response.target,
            disease=response.disease,
            science_score=scores.science_score,
            regulatory_score=scores.regulatory_score,
            combined_score=scores.combined_score,
            recommendation=scores.recommendation,
            science_evidence=str(response.scientific_evidence)[:3000],
            pathway=reg.recommended_pathway or "Unknown",
            designations=", ".join(d.value for d in reg.special_designations) or "None",
            timeline=reg.estimated_timeline_years or "Unknown",
            cost=reg.estimated_cost_range or "Unknown",
            reasoning="\n".join(f"  - {r}" for r in reg.reasoning),
            cost_estimate=cost_estimate_text,
            patent_radar=patent_radar_text,
            flag_count=len(response.flags),
            flags=_format_flags(response.flags),
            data_sources=_format_data_sources(response.data_sources),
        )

        completion = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content

    except Exception as e:
        return f"LLM synthesis unavailable: {str(e)}"

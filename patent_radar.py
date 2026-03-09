"""
patent_radar.py — Drug Target Patent Landscape Scanner

Architecture adapted from compl_ai/systems/ip_radar.py:
  that project scanned USPTO patents for medical device freedom-to-operate risk,
  using PatentsView API + LLM relevance assessment with traffic-light ratings.

This module applies the same pattern at drug-target scale:
  - Queries are generated from target gene + disease + mechanism (vs. device profile)
  - PatentsView API unchanged — same endpoint, same JSON query syntax
  - LLM relevance prompt rewritten for drug composition-of-matter / method-of-use claims
  - Traffic-light logic unchanged (GREEN/YELLOW/RED)
  - Expiration estimate unchanged (20 years from priority date)

WHAT THIS DOES:
  Searches for patents covering:
    1. The target protein itself (composition of matter / antibody claims)
    2. Target-disease method-of-use combinations
    3. Known drugs/compounds in the target's pipeline
    4. Key mechanistic pathway claims

WHAT THIS DOES NOT DO:
  - Full Freedom-to-Operate analysis (requires claim-level parsing + legal judgment)
  - Continuation/divisional family tracking
  - Prosecution history lookup
  Always consult a registered patent attorney before making IP decisions.

Sources: USPTO PatentsView API (public, no auth required)
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from models import DrugPatentResult, PatentRadarResult, PatentRelevance

logger = logging.getLogger(__name__)

PATENTSVIEW_API   = "https://api.patentsview.org/patents/query"
MAX_PATENTS_FETCH = 20   # raw results to fetch before LLM ranking
MAX_PATENTS_ANALYZE = 10  # patents to run through LLM (API calls are expensive)


# ---------------------------------------------------------------------------
# Step 1: Build search queries from target + disease context
# ---------------------------------------------------------------------------

def _build_search_queries(target: str, disease: str, known_drugs: list[str]) -> list[str]:
    """
    Generate 4 diverse patent search queries covering:
      1. Target protein name (composition of matter / antibody)
      2. Target + disease method-of-use
      3. Known drugs / compounds (if any)
      4. Mechanism / pathway angle
    """
    queries = [
        target,                              # gene/protein name alone — broadest
        f"{target} {disease}",               # target-disease pair (method of use)
        f"{target} inhibitor antagonist",    # mechanistic angle
    ]
    # Add drug-name query if Open Targets found compounds in the pipeline
    if known_drugs:
        queries.append(" ".join(known_drugs[:3]))  # top 3 drug names
    else:
        queries.append(f"{disease} treatment therapy")
    return queries[:4]


# ---------------------------------------------------------------------------
# Step 2: USPTO PatentsView API fetch
# ---------------------------------------------------------------------------

def _search_patentsview(query: str, limit: int = 8) -> list[dict]:
    """
    Query the PatentsView API (USPTO public data).
    Uses full-text abstract search — same approach as compl_ai ip_radar.py.
    """
    payload = {
        "q": {"_text_any": {"patent_abstract": query}},
        "f": [
            "patent_number", "patent_title", "patent_abstract",
            "assignee_organization", "patent_date", "app_date",
        ],
        "o": {"per_page": limit},
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(PATENTSVIEW_API, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("patents") or []
    except Exception as e:
        logger.warning("PatentsView API error for query '%s': %s", query, e)
        return []


def _normalize_patent(raw: dict) -> dict:
    """Normalise PatentsView result to a common internal dict."""
    assignee_orgs = raw.get("assignees") or []
    assignee = assignee_orgs[0].get("assignee_organization", "Unknown") if assignee_orgs else "Unknown"

    app_dates = raw.get("applications") or []
    app_date = app_dates[0].get("app_date", "") if app_dates else ""

    # Rough expiration: 20 years from application date (same calc as compl_ai)
    expiration = ""
    if app_date and len(app_date) >= 4:
        try:
            expiration = str(int(app_date[:4]) + 20) + app_date[4:]
        except ValueError:
            pass

    return {
        "patent_number":   raw.get("patent_number", ""),
        "title":           raw.get("patent_title", ""),
        "abstract":        raw.get("patent_abstract", "") or "",
        "assignee":        assignee,
        "filing_date":     app_date,
        "grant_date":      raw.get("patent_date", ""),
        "expiration_date": expiration,
    }


def _fetch_all_patents(queries: list[str]) -> list[dict]:
    """Run all queries; return deduplicated list up to MAX_PATENTS_FETCH."""
    all_patents: list[dict] = []
    seen: set[str] = set()
    per_query = max(3, MAX_PATENTS_FETCH // len(queries))

    for query in queries:
        for raw in _search_patentsview(query, limit=per_query):
            normalized = _normalize_patent(raw)
            num = normalized["patent_number"]
            if num and num not in seen:
                seen.add(num)
                all_patents.append(normalized)

    logger.info("Patent radar: %d unique patents fetched for target", len(all_patents))
    return all_patents[:MAX_PATENTS_FETCH]


# ---------------------------------------------------------------------------
# Step 3: LLM relevance assessment (drug-specific)
# ---------------------------------------------------------------------------

_RELEVANCE_SYSTEM = """You are a patent attorney's assistant specializing in pharmaceutical and biotech IP.

Your job is to assess whether a patent could pose freedom-to-operate risk for a drug development program
targeting a specific protein in a specific disease.

Given:
1. The drug target (gene/protein name) and disease indication
2. A patent title and abstract

Assess:
- Whether the patent's claims might cover: (a) the target protein itself, (b) methods of treating
  the disease by modulating this target, or (c) compounds/antibodies that bind this target
- Which specific aspects create overlap
- A relevance rating: "green" (not relevant), "yellow" (possible overlap), or "red" (high overlap risk)

Rating guide:
  green: Patent covers different target/mechanism, is clearly expired, or has no drug-relevant claims
  yellow: Adjacent technology, partial overlap, or uncertain expiration — worth attorney review
  red: Directly covers the target protein, the target-disease method of use, or known lead compounds

Return JSON:
{
  "relevance": "green" | "yellow" | "red",
  "explanation": "2-3 sentence plain-English explanation",
  "concerning_claims": ["specific claim language or aspects of concern, empty if green"],
  "is_likely_active": true | false
}

IMPORTANT: Be conservative — when uncertain, rate yellow not green. Do NOT provide legal advice."""


def _assess_relevance(patent: dict, target: str, disease: str) -> dict:
    """Run LLM relevance assessment for one patent. Returns safe default on failure."""
    import anthropic
    client = anthropic.Anthropic()

    message_text = (
        f"DRUG TARGET: {target}\n"
        f"DISEASE INDICATION: {disease}\n\n"
        f"PATENT TITLE: {patent.get('title', 'N/A')}\n\n"
        f"PATENT ABSTRACT:\n{patent.get('abstract', 'N/A')[:800]}\n"
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",   # fast + cheap for bulk assessment
            max_tokens=400,
            system=_RELEVANCE_SYSTEM,
            messages=[{"role": "user", "content": message_text}],
        )
        import json as _json
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return _json.loads(text)
    except Exception as e:
        logger.warning("Patent relevance assessment failed for %s: %s", patent.get("patent_number"), e)
        return {
            "relevance": "yellow",
            "explanation": "Automated relevance assessment failed. Manual review recommended.",
            "concerning_claims": [],
            "is_likely_active": True,
        }


def _is_active(patent: dict, relevance_data: dict) -> bool:
    """Determine whether a patent is likely still in force."""
    if not relevance_data.get("is_likely_active", True):
        return False
    expiration = patent.get("expiration_date", "")
    if expiration and len(expiration) >= 4:
        try:
            if int(expiration[:4]) < 2026:
                return False
        except ValueError:
            pass
    return True


def _map_relevance(relevance_str: str, is_active: bool) -> PatentRelevance:
    if not is_active:
        return PatentRelevance.GREEN
    return {
        "green":  PatentRelevance.GREEN,
        "yellow": PatentRelevance.YELLOW,
        "red":    PatentRelevance.RED,
    }.get(relevance_str.lower(), PatentRelevance.YELLOW)


# ---------------------------------------------------------------------------
# Step 4: IP landscape summary
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = """You are a biotech IP strategist helping a drug development team understand
their patent landscape for a specific target-disease program.

Given findings from a patent search, write a concise 3-4 sentence plain-English summary covering:
1. Overall IP density (crowded vs. open landscape for this target/indication)
2. Most significant risk areas (assignees, claim types, expiry timelines)
3. Single most important action for the team

Be direct and practical. One brief phrase acknowledging this is not legal advice is sufficient.
Do NOT list individual patents — synthesize the landscape."""


def _generate_summary(target: str, disease: str, patents: list[DrugPatentResult]) -> str:
    import anthropic
    client = anthropic.Anthropic()

    red_count    = sum(1 for p in patents if p.relevance == PatentRelevance.RED)
    yellow_count = sum(1 for p in patents if p.relevance == PatentRelevance.YELLOW)

    msg = (
        f"Drug target: {target} | Disease: {disease}\n"
        f"Search returned {len(patents)} potentially relevant patents:\n"
        f"  High risk (red): {red_count}\n"
        f"  Moderate concern (yellow): {yellow_count}\n"
        f"  Low concern (green): {len(patents) - red_count - yellow_count}\n\n"
        "Most concerning patents:\n"
    )
    sort_order = {PatentRelevance.RED: 0, PatentRelevance.YELLOW: 1, PatentRelevance.GREEN: 2}
    for p in sorted(patents, key=lambda x: sort_order[x.relevance])[:3]:
        msg += f"  - {p.title} ({p.patent_number}, {p.assignee}): {p.relevance_explanation[:120]}\n"

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=_SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": msg}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("Patent summary generation failed: %s", e)
        return (
            f"Patent search identified {len(patents)} potentially relevant patents "
            f"({red_count} high-risk, {yellow_count} moderate concern). "
            "Consult a registered patent attorney for a formal Freedom-to-Operate analysis."
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_patent_radar(
    target: str,
    disease: str,
    known_drug_names: Optional[list[str]] = None,
) -> PatentRadarResult:
    """
    Run the patent landscape scan for a drug target-disease pair.

    Steps (mirroring compl_ai ip_radar.run_ip_radar):
      1. Build diverse search queries from target + disease context
      2. Fetch patents via USPTO PatentsView API
      3. Assess each patent's relevance with LLM (Haiku — fast/cheap)
      4. Generate plain-English IP landscape summary

    Args:
        target:           Gene/protein name (e.g. "KRAS G12C")
        disease:          Disease indication (e.g. "non-small cell lung cancer")
        known_drug_names: Compound names from Open Targets (for query enrichment)

    Returns:
        PatentRadarResult with per-patent assessments and landscape summary.
    """
    queries = _build_search_queries(target, disease, known_drug_names or [])
    logger.info("Patent radar queries: %s", queries)

    raw_patents = _fetch_all_patents(queries)

    if not raw_patents:
        logger.warning("Patent radar: no results returned from PatentsView API")
        return PatentRadarResult(
            patents=[],
            search_queries_used=queries,
            red_count=0,
            yellow_count=0,
            summary=(
                "Patent searches returned no results. This may indicate an open IP space, "
                "or may reflect API limitations. Manual search on USPTO and Google Patents "
                "is recommended before advancing to clinical development."
            ),
        )

    # Assess relevance for top patents — run all LLM calls concurrently
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _assess_one(raw: dict) -> DrugPatentResult:
        relevance_data = _assess_relevance(raw, target, disease)
        active = _is_active(raw, relevance_data)
        relevance_enum = _map_relevance(relevance_data.get("relevance", "yellow"), active)
        result = DrugPatentResult(
            patent_number=raw.get("patent_number", "Unknown"),
            title=raw.get("title", "Unknown"),
            abstract=raw.get("abstract", ""),
            assignee=raw.get("assignee", "Unknown"),
            filing_date=raw.get("filing_date", ""),
            expiration_date=raw.get("expiration_date") or None,
            is_active=active,
            relevance=relevance_enum,
            relevance_explanation=relevance_data.get("explanation", ""),
            concerning_claims=relevance_data.get("concerning_claims", []),
        )
        logger.info("  %s → %s (%s)", result.patent_number, result.relevance.value, result.assignee)
        return result

    to_analyze = raw_patents[:MAX_PATENTS_ANALYZE]
    analyzed: list[DrugPatentResult] = []
    with ThreadPoolExecutor(max_workers=min(len(to_analyze), 5)) as pool:
        futures = [pool.submit(_assess_one, raw) for raw in to_analyze]
        for future in as_completed(futures):
            try:
                analyzed.append(future.result())
            except Exception as e:
                logger.warning("Patent assessment future failed: %s", e)

    # Sort red → yellow → green
    sort_order = {PatentRelevance.RED: 0, PatentRelevance.YELLOW: 1, PatentRelevance.GREEN: 2}
    analyzed.sort(key=lambda p: sort_order[p.relevance])

    red_count    = sum(1 for p in analyzed if p.relevance == PatentRelevance.RED)
    yellow_count = sum(1 for p in analyzed if p.relevance == PatentRelevance.YELLOW)

    summary = _generate_summary(target, disease, analyzed)

    return PatentRadarResult(
        patents=analyzed,
        search_queries_used=queries,
        red_count=red_count,
        yellow_count=yellow_count,
        summary=summary,
    )

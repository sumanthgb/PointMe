"""
workers/pubmed.py — Worker 3: PubMed E-utilities

API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
Two-step pipeline: esearch (get PMIDs) → efetch (get abstracts + metadata).
Note: PubMed doesn't provide citation counts natively.
      We compute a recency-weighted relevance score instead.
"""

import time
# httpx imported lazily inside functions (avoids import errors in test environments)
import xml.etree.ElementTree as ET
from datetime import datetime
from models import PubMedResult, Paper, WorkerMeta, WorkerStatus
from config import PUBMED_MAX_RESULTS

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EINFO_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi"

CURRENT_YEAR = datetime.now().year


def _compute_relevance_score(papers: list[Paper], total_count: int) -> float:
    """
    Heuristic relevance score (0-1) based on:
    - Volume of literature (log-normalized)
    - Recency of top papers
    """
    if not papers:
        return 0.0

    import math
    # Volume component: log scale, 1000+ papers = max score
    volume_score = min(math.log10(max(total_count, 1)) / 3.0, 1.0)

    # Recency component: average recency of top papers
    recency_scores = []
    for paper in papers:
        age = CURRENT_YEAR - paper.year
        # Papers < 2 years old score 1.0, decays over 10 years
        recency_scores.append(max(0.0, 1.0 - (age / 10.0)))
    recency_score = sum(recency_scores) / len(recency_scores)

    return round((volume_score * 0.5) + (recency_score * 0.5), 3)


def _parse_pubmed_xml(xml_text: str) -> list[Paper]:
    """Parse PubMed efetch XML into Paper objects."""
    papers = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return papers

    for article in root.findall(".//PubmedArticle"):
        try:
            # PMID
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # Title
            title_el = article.find(".//ArticleTitle")
            title = (title_el.text or "") if title_el is not None else ""

            # Abstract (may have multiple AbstractText sections)
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(
                (el.text or "") for el in abstract_parts if el.text
            )

            # Year — PubMed XML has several possible locations, try all in order
            year = None
            for xpath in [
                ".//PubDate/Year",          # Journal PubDate (most common)
                ".//ArticleDate/Year",      # Electronic publication date
                ".//PubMedPubDate/Year",    # History dates (pubmed, medline, etc.)
                ".//MedlineDate",           # Fallback: "2021 Jan-Feb" format
            ]:
                el = article.find(xpath)
                if el is not None and el.text:
                    try:
                        year = int(el.text[:4])
                        break
                    except ValueError:
                        continue
            if year is None:
                year = CURRENT_YEAR

            # Journal
            journal_el = article.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else None

            papers.append(Paper(
                pmid=pmid,
                title=title,
                abstract=abstract[:1000],  # truncate for payload size
                year=year,
                journal=journal,
                citation_count=0  # PubMed doesn't provide this; placeholder
            ))
        except Exception:
            continue  # skip malformed records

    return papers


def fetch_pubmed(target: str, disease: str) -> PubMedResult:
    """
    Search PubMed for papers on target-disease pair.

    Args:
        target:  e.g. "KRAS G12C"
        disease: e.g. "non-small cell lung cancer"

    Returns:
        PubMedResult with top papers and a computed relevance score.
    """
    start = time.time()
    query = f"{target}[tiab] AND {disease}[tiab]"

    try:
        import httpx
        with httpx.Client(timeout=30) as client:

            # Step 1: esearch — get PMIDs sorted by relevance
            search_resp = client.get(ESEARCH_URL, params={
                "db": "pubmed",
                "term": query,
                "retmax": PUBMED_MAX_RESULTS,
                "retmode": "json",
                "sort": "relevance",
                "usehistory": "y",   # use server-side history for large sets
            })
            search_resp.raise_for_status()
            search_data = search_resp.json()

            esearch = search_data.get("esearchresult", {})
            pmids = esearch.get("idlist", [])
            total_count = int(esearch.get("count", 0))

            if not pmids:
                return PubMedResult(
                    total_papers=total_count,
                    papers=[],
                    relevance_score=0.0,
                    meta=WorkerMeta(
                        status=WorkerStatus.PARTIAL,
                        query_time_ms=int((time.time() - start) * 1000),
                        error="No papers found for query"
                    )
                )

            # Step 2: efetch — get full records for those PMIDs
            fetch_resp = client.post(EFETCH_URL, data={
                "db": "pubmed",
                "id": ",".join(pmids),
                "rettype": "abstract",
                "retmode": "xml",
            })
            fetch_resp.raise_for_status()

            papers = _parse_pubmed_xml(fetch_resp.text)
            relevance_score = _compute_relevance_score(papers, total_count)

            elapsed = int((time.time() - start) * 1000)
            return PubMedResult(
                total_papers=total_count,
                papers=papers,
                relevance_score=relevance_score,
                meta=WorkerMeta(status=WorkerStatus.SUCCESS, query_time_ms=elapsed)
            )

    except Exception as e:
        return PubMedResult(
            meta=WorkerMeta(
                status=WorkerStatus.FAILED,
                query_time_ms=int((time.time() - start) * 1000),
                error=str(e)
            )
        )

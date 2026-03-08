"""
workers/orange_book.py — Worker 6: FDA Orange Book

Source: https://open.fda.gov/apis/drug/nda/ 
        + https://www.fda.gov/media/76860/download (downloadable dataset)

Patent and exclusivity data for comparable drugs.
Used by the scoring engine to assess IP crowding / freedom to operate.

Note: The openFDA NDA endpoint is limited. For best results, supplement with
the downloadable Orange Book dataset (products.zip, patent.zip, exclusivity.zip).
This stub implements the API approach; the download approach is noted as an upgrade.
"""

import time
# httpx imported lazily inside functions (avoids import errors in test environments)
from models import OrangeBookResult, ComparableDrug, WorkerMeta, WorkerStatus

# openFDA NDA search endpoint
NDA_URL = "https://api.fda.gov/drug/nda.json"

# Alternatively, use the Orange Book data files directly:
# https://www.fda.gov/media/76860/download  (products)
# https://www.fda.gov/media/76862/download  (patent)
# https://www.fda.gov/media/76861/download  (exclusivity)
# These are tab-separated .txt files — more reliable, but require a download step


def _compute_ip_crowding_score(drugs: list[ComparableDrug]) -> float:
    """
    Estimate IP crowding based on how many comparable drugs have active exclusivity.
    Higher score = more crowded = harder to enter market.
    """
    if not drugs:
        return 0.0

    from datetime import datetime
    now = datetime.now()
    active_exclusivity_count = 0

    for drug in drugs:
        if drug.exclusivity_expiration:
            try:
                exp = datetime.strptime(drug.exclusivity_expiration, "%m/%d/%Y")
                if exp > now:
                    active_exclusivity_count += 1
            except ValueError:
                pass

    # Normalise: 0 active = 0.0, 5+ active = 1.0
    return min(active_exclusivity_count / 5.0, 1.0)


def fetch_orange_book(target: str, disease: str) -> OrangeBookResult:
    """
    Fetch patent and exclusivity data for comparable drugs from FDA Orange Book.

    Args:
        target:  Gene/protein name, e.g. "KRAS G12C"
        disease: Disease name for context

    Returns:
        OrangeBookResult with comparable drug IP landscape.
    """
    start = time.time()
    search_term = target.split()[0].lower()

    try:
        import httpx
        with httpx.Client(timeout=30) as client:
            resp = client.get(NDA_URL, params={
                "search": f'products.active_ingredients.name:"{search_term}"',
                "limit": 20,
            })

            if resp.status_code == 404:
                # Try by brand name
                resp = client.get(NDA_URL, params={
                    "search": f'products.brand_name:"{search_term}"',
                    "limit": 20,
                })

            if resp.status_code == 404:
                return OrangeBookResult(
                    meta=WorkerMeta(
                        status=WorkerStatus.PARTIAL,
                        query_time_ms=int((time.time() - start) * 1000),
                        error=f"No Orange Book records found for '{search_term}'"
                    )
                )

            resp.raise_for_status()
            data = resp.json()

        comparable_drugs = []
        for result in data.get("results", []):
            for product in result.get("products", []):
                active_ingredients = product.get("active_ingredients", [{}])
                name = active_ingredients[0].get("name", "Unknown") if active_ingredients else "Unknown"

                # Patent and exclusivity data lives in nested fields
                # The openFDA NDA endpoint has limited patent data vs the downloadable dataset
                # These fields may be empty — handled gracefully by the model
                comparable_drugs.append(ComparableDrug(
                    name=name,
                    exclusivity_type=product.get("te_code"),       # Therapeutic Equivalence code
                    exclusivity_expiration=None,                    # Not in NDA endpoint; use download
                    patent_number=None,                             # Not in NDA endpoint; use download
                    patent_expiration=None,                         # Not in NDA endpoint; use download
                ))

        # Deduplicate
        seen = set()
        deduped = []
        for d in comparable_drugs:
            if d.name not in seen:
                deduped.append(d)
                seen.add(d.name)

        ip_score = _compute_ip_crowding_score(deduped)

        elapsed = int((time.time() - start) * 1000)
        return OrangeBookResult(
            comparable_drugs=deduped,
            ip_crowding_score=ip_score,
            meta=WorkerMeta(status=WorkerStatus.SUCCESS, query_time_ms=elapsed)
        )

    except Exception as e:
        return OrangeBookResult(
            meta=WorkerMeta(
                status=WorkerStatus.FAILED,
                query_time_ms=int((time.time() - start) * 1000),
                error=str(e)
            )
        )

# ---------------------------------------------------------------------------
# UPGRADE PATH: Download-based Orange Book (more reliable)
# ---------------------------------------------------------------------------
# If the API approach proves too limited, use this instead:
#
# import urllib.request, zipfile, io, csv
#
# def fetch_orange_book_from_download(target: str) -> OrangeBookResult:
#     """Download and parse the Orange Book flat files directly from FDA."""
#     # Products file
#     url = "https://www.fda.gov/media/76860/download"
#     with urllib.request.urlopen(url) as r:
#         zf = zipfile.ZipFile(io.BytesIO(r.read()))
#         with zf.open("products.txt") as f:
#             reader = csv.DictReader(io.TextIOWrapper(f), delimiter="~")
#             for row in reader:
#                 if target.lower() in row.get("Ingredient", "").lower():
#                     ...  # parse patent/exclusivity fields

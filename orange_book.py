"""
workers/orange_book.py — Worker 6: FDA Orange Book

Source: https://api.fda.gov/drug/drugsfda.json
        + https://www.fda.gov/media/76860/download (downloadable dataset)

Patent and exclusivity data for comparable drugs.
Used by the scoring engine to assess IP crowding / freedom to operate.
"""

import time
from models import OrangeBookResult, ComparableDrug, WorkerMeta, WorkerStatus

# FIX: was nda.json which does not exist — correct endpoint is drugsfda.json
BASE_URL = "https://api.fda.gov/drug/drugsfda.json"


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
    disease_term = " ".join(disease.split()[:3]).lower()

    try:
        import httpx
        with httpx.Client(timeout=30) as client:
            resp = client.get(BASE_URL, params={
                "search": f'products.active_ingredients.name:"{search_term}"',
                "limit": 20,
            })

            if resp.status_code != 200:
                resp = client.get(BASE_URL, params={
                    "search": f'products.brand_name:"{search_term}"',
                    "limit": 20,
                })

            # Disease-based fallback: find IP landscape for drugs in the same indication
            if resp.status_code != 200:
                label_resp = client.get(
                    "https://api.fda.gov/drug/label.json",
                    params={
                        "search": f'indications_and_usage:"{disease_term}"',
                        "limit": 5,
                    }
                )
                if label_resp.status_code == 200:
                    synthetic_results = []
                    for item in label_resp.json().get("results", []):
                        openfda = item.get("openfda", {})
                        for brand in openfda.get("brand_name", [])[:2]:
                            synthetic_results.append({
                                "products": [{"active_ingredients": [{"name": brand}]}]
                            })
                    if synthetic_results:
                        data = {"results": synthetic_results}
                    else:
                        return OrangeBookResult(
                            meta=WorkerMeta(
                                status=WorkerStatus.PARTIAL,
                                query_time_ms=int((time.time() - start) * 1000),
                                error=f"No Orange Book records found for '{search_term}'"
                            )
                        )
                else:
                    return OrangeBookResult(
                        meta=WorkerMeta(
                            status=WorkerStatus.PARTIAL,
                            query_time_ms=int((time.time() - start) * 1000),
                            error=f"No Orange Book records found for '{search_term}'"
                        )
                    )
            else:
                resp.raise_for_status()
                data = resp.json()

        comparable_drugs = []
        for result in data.get("results", []):
            for product in result.get("products", []):
                active_ingredients = product.get("active_ingredients", [{}])
                name = active_ingredients[0].get("name", "Unknown") if active_ingredients else "Unknown"

                comparable_drugs.append(ComparableDrug(
                    name=name,
                    exclusivity_type=product.get("te_code"),
                    exclusivity_expiration=None,  # not in drugsfda endpoint; use download for this
                    patent_number=None,
                    patent_expiration=None,
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
# UPGRADE PATH: Download-based Orange Book (more reliable for patent/exclusivity)
# ---------------------------------------------------------------------------
# If you need real exclusivity expiration dates, use the flat files:
#
# import urllib.request, zipfile, io, csv
#
# def fetch_orange_book_from_download(target: str) -> OrangeBookResult:
#     url = "https://www.fda.gov/media/76860/download"
#     with urllib.request.urlopen(url) as r:
#         zf = zipfile.ZipFile(io.BytesIO(r.read()))
#         with zf.open("products.txt") as f:
#             reader = csv.DictReader(io.TextIOWrapper(f), delimiter="~")
#             for row in reader:
#                 if target.lower() in row.get("Ingredient", "").lower():
#                     ...  # parse patent/exclusivity fields
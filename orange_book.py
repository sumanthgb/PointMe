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

    try:
        import urllib.request
        import urllib.parse
        import json

        # Try active ingredient name first
        params = {"search": f'products.active_ingredients.name:"{search_term}"', "limit": 20}
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}?{query_string}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                all_results = data.get("results", [])
        except Exception:
            # Try brand name fallback
            params = {"search": f'products.brand_name:"{search_term}"', "limit": 20}
            query_string = urllib.parse.urlencode(params)
            url = f"{BASE_URL}?{query_string}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode())
                    all_results = data.get("results", [])
            except Exception:
                all_results = []

        if not all_results:
            return OrangeBookResult(
                meta=WorkerMeta(
                    status=WorkerStatus.PARTIAL,
                    query_time_ms=int((time.time() - start) * 1000),
                    error=f"No Orange Book records found for '{search_term}'"
                )
            )

        comparable_drugs = []
        for result in all_results:
            for product in result.get("products", []):
                active_ingredients = product.get("active_ingredients", [{}])
                name = active_ingredients[0].get("name", "Unknown") if active_ingredients else "Unknown"

                comparable_drugs.append(ComparableDrug(
                    name=name,
                    exclusivity_type=product.get("te_code"),
                    exclusivity_expiration=None,
                    patent_number=None,
                    patent_expiration=None,
                ))

        # Deduplicate
        seen = set()
        deduped = []
        for d in comparable_drugs:
            if d.name not in seen and d.name != "Unknown":
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


def supplement_with_drug_names(ob_result: OrangeBookResult, drug_names: list[str]) -> OrangeBookResult:
    """
    Search Orange Book by known drug names to supplement the gene-based search.
    """
    if not drug_names or ob_result.meta.status == WorkerStatus.FAILED:
        return ob_result

    import urllib.request
    import urllib.parse
    import json

    seen_names: set[str] = {d.name for d in ob_result.comparable_drugs}
    extra_drugs: list[ComparableDrug] = []

    try:
        for drug in drug_names[:10]:
            params = {"search": f'products.active_ingredients.name:"{drug}"', "limit": 10}
            query_string = urllib.parse.urlencode(params)
            url = f"{BASE_URL}?{query_string}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode())
                    results = data.get("results", [])
            except Exception:
                continue

            for result in results:
                for product in result.get("products", []):
                    active_ingredients = product.get("active_ingredients", [{}])
                    name = active_ingredients[0].get("name", "Unknown") if active_ingredients else "Unknown"
                    if name in seen_names or name == "Unknown":
                        continue
                    seen_names.add(name)
                    extra_drugs.append(ComparableDrug(
                        name=name,
                        exclusivity_type=product.get("te_code"),
                        exclusivity_expiration=None,
                        patent_number=None,
                        patent_expiration=None,
                    ))
    except Exception:
        pass

    merged = ob_result.comparable_drugs + extra_drugs
    return OrangeBookResult(
        comparable_drugs=merged,
        ip_crowding_score=_compute_ip_crowding_score(merged),
        meta=ob_result.meta,
    )
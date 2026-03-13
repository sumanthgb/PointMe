"""
workers/fda_drugs.py — Worker 5: Drugs@FDA via openFDA API

API: https://api.fda.gov/drug/drugsfda.json
Fetches approved and rejected drugs by active ingredient or pharmacologic class.
"""

import time
from models import FDADrugsResult, FDADrug, WorkerMeta, WorkerStatus

BASE_URL = "https://api.fda.gov/drug/drugsfda.json"

APPROVED_ACTIONS = {"AP", "TA"}       # Approved, Tentative Approval
REJECTED_ACTIONS = {"RTF", "REF", "WD"}  # Refuse to File, Refuse, Withdrawn


def _parse_drug(product: dict, submission: dict) -> FDADrug:
    """Build an FDADrug from an openFDA product + submission combo."""
    active_ingredients = product.get("active_ingredients", [{}])
    drug_name = active_ingredients[0].get("name", "Unknown") if active_ingredients else "Unknown"

    return FDADrug(
        name=drug_name,
        approval_date=submission.get("submission_status_date"),
        application_type=submission.get("application_type", ""),
        application_number=product.get("application_number"),
        pathway=_infer_pathway(submission),
        sponsor=None,
        mechanism_of_action=None,
    )


def _infer_pathway(submission: dict) -> str:
    """Infer approval pathway from submission review priority."""
    priority = submission.get("review_priority", "STANDARD").upper()
    submission_type = submission.get("submission_type", "").upper()

    if "PRIORITY" in priority:
        return "Priority Review"
    if "ACCELERATED" in submission_type or "AA" in submission_type:
        return "Accelerated Approval"
    if "BREAKTHROUGH" in submission_type:
        return "Breakthrough Therapy"
    return "Standard"


def fetch_fda_drugs(target: str, disease: str) -> FDADrugsResult:
    """
    Search Drugs@FDA for approved/rejected drugs related to this target.

    Args:
        target:  Gene/protein name, e.g. "KRAS G12C"
        disease: Disease name (context only)

    Returns:
        FDADrugsResult with approved and rejected drug lists.
    """
    start = time.time()
    search_term = target.split()[0].lower()

    try:
        import urllib.request
        import urllib.parse
        import json
        
        # 1. First try active ingredient name
        params = {"search": f'products.active_ingredients.name:"{search_term}"', "limit": 50}
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}?{query_string}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                all_results = data.get("results", [])
        except Exception:
            # 2. If 404, try brand name
            params = {"search": f'products.brand_name:"{search_term}"', "limit": 50}
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
            return FDADrugsResult(
                meta=WorkerMeta(
                    status=WorkerStatus.PARTIAL,
                    query_time_ms=int((time.time() - start) * 1000),
                    error=f"No FDA drug records found for '{search_term}'"
                )
            )

        approved_drugs = []
        rejected_drugs = []

        for result in all_results:
            for submission in result.get("submissions", []):
                action = submission.get("submission_status", "").upper()
                for product in result.get("products", []):
                    drug = _parse_drug(product, submission)
                    if action in APPROVED_ACTIONS:
                        approved_drugs.append(drug)
                    elif action in REJECTED_ACTIONS:
                        rejected_drugs.append(drug)

        # Deduplicate by name
        seen = set()
        deduped_approved = []
        for d in approved_drugs:
            if d.name not in seen and d.name != "Unknown":
                deduped_approved.append(d)
                seen.add(d.name)

        # We leave this empty because openFDA doesn't give us MOA reliably
        approved_drugs_same_moa = []

        elapsed = int((time.time() - start) * 1000)
        return FDADrugsResult(
            approved_drugs=deduped_approved,
            rejected_drugs=rejected_drugs,
            approved_drugs_same_moa=approved_drugs_same_moa,
            meta=WorkerMeta(status=WorkerStatus.SUCCESS, query_time_ms=elapsed)
        )

    except Exception as e:
        return FDADrugsResult(
            meta=WorkerMeta(
                status=WorkerStatus.FAILED,
                query_time_ms=int((time.time() - start) * 1000),
                error=str(e)
            )
        )

def supplement_with_drug_names(fda_result: FDADrugsResult, drug_names: list[str]) -> FDADrugsResult:
    """
    Search FDA by known drug names to supplement the gene-based search.
    """
    if not drug_names or fda_result.meta.status == WorkerStatus.FAILED:
        return fda_result

    import urllib.request
    import urllib.parse
    import json
    
    seen_names: set[str] = {d.name for d in fda_result.approved_drugs + fda_result.rejected_drugs}
    
    appr_extra: list[FDADrug] = []
    rej_extra: list[FDADrug] = []

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
                for submission in result.get("submissions", []):
                    action = submission.get("submission_status", "").upper()
                    for product in result.get("products", []):
                        parsed_drug = _parse_drug(product, submission)
                        if parsed_drug.name in seen_names or parsed_drug.name == "Unknown":
                            continue
                        seen_names.add(parsed_drug.name)
                        
                        if action in APPROVED_ACTIONS:
                            appr_extra.append(parsed_drug)
                        elif action in REJECTED_ACTIONS:
                            rej_extra.append(parsed_drug)
    except Exception:
        pass
        
    return FDADrugsResult(
        approved_drugs=fda_result.approved_drugs + appr_extra,
        rejected_drugs=fda_result.rejected_drugs + rej_extra,
        approved_drugs_same_moa=fda_result.approved_drugs_same_moa,
        meta=fda_result.meta
    )
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


def _search_fda(client, search_query: str, limit: int = 50) -> list:
    """Run a single openFDA drugsfda query, return results list or []."""
    resp = client.get(BASE_URL, params={"search": search_query, "limit": limit})
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []


def fetch_fda_drugs(target: str, disease: str) -> FDADrugsResult:
    """
    Search Drugs@FDA for approved/rejected drugs related to this target.

    Args:
        target:  Gene/protein name, e.g. "KRAS G12C"
        disease: Disease name

    Returns:
        FDADrugsResult with approved and rejected drug lists.
    """
    start = time.time()
    search_term = target.split()[0].lower()
    # Shorten disease to first 2-3 words to improve FDA search hit rate
    disease_term = " ".join(disease.split()[:3]).lower()

    try:
        import httpx
        with httpx.Client(timeout=30) as client:
            # Query 1: by active ingredient (works for targets that ARE drugs, e.g. PCSK9 → evolocumab)
            results = _search_fda(client, f'products.active_ingredients.name:"{search_term}"')

            # Query 2: by brand name fallback
            if not results:
                results = _search_fda(client, f'products.brand_name:"{search_term}"')

            # Query 3: by indication/disease — finds approved drugs IN the same disease space
            # (critical for targets like BACE1 where no drug is named "bace1" but
            #  lecanemab/donanemab are approved for Alzheimer's disease)
            disease_results = _search_fda(
                client,
                f'products.active_ingredients.name:"{disease_term}"',
                limit=20
            )
            # Use openfda label indication search as disease fallback
            if not disease_results:
                label_resp = client.get(
                    "https://api.fda.gov/drug/label.json",
                    params={
                        "search": f'indications_and_usage:"{disease_term}"',
                        "limit": 10,
                    }
                )
                if label_resp.status_code == 200:
                    for item in label_resp.json().get("results", []):
                        openfda = item.get("openfda", {})
                        brand_names = openfda.get("brand_name", [])
                        app_numbers = openfda.get("application_number", [])
                        for i, brand in enumerate(brand_names[:3]):
                            app_num = app_numbers[i] if i < len(app_numbers) else None
                            results.append({
                                "_from_label": True,
                                "brand_name": brand,
                                "application_number": app_num,
                            })

            if not results:
                return FDADrugsResult(
                    meta=WorkerMeta(
                        status=WorkerStatus.PARTIAL,
                        query_time_ms=int((time.time() - start) * 1000),
                        error=f"No FDA drug records found for '{search_term}' or '{disease_term}'"
                    )
                )

            data = {"results": results}

        approved_drugs = []
        rejected_drugs = []

        for result in data.get("results", []):
            # Handle label-sourced entries (disease fallback)
            if result.get("_from_label"):
                approved_drugs.append(FDADrug(
                    name=result.get("brand_name", "Unknown"),
                    approval_date=None,
                    application_type="NDA/BLA",
                    application_number=result.get("application_number"),
                    pathway="Standard",
                    sponsor=None,
                    mechanism_of_action=None,
                ))
                continue

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
            if d.name not in seen:
                deduped_approved.append(d)
                seen.add(d.name)

        # FIX: approved_drugs_same_moa was incorrectly set to deduped_approved[:5],
        # which would wrongly trigger 505(b)(2) pathway for any target that has
        # *any* approved drug, regardless of mechanism. The openFDA endpoint does
        # not return mechanism-of-action data, so we cannot determine same-MOA here.
        # Setting to [] correctly defaults the regulatory engine to 505(b)(1).
        # Aparna can populate this with manual MOA lookups if needed for the demo.
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
"""
workers/open_targets.py — Worker 1: Open Targets Platform API

API: https://api.platform.opentargets.org/api/v4/graphql
GraphQL — queries for genetic associations, known drugs, tractability, pathways.

Real implementation: uncomment the httpx calls and replace stub returns.
"""

import time
# httpx imported lazily inside functions (avoids import errors in test environments)
from models import OpenTargetsResult, GeneticAssociation, KnownDrug, WorkerMeta, WorkerStatus
from config import OPENTARGETS_MAX_DRUGS

OPENTARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"


# ---------------------------------------------------------------------------
# GraphQL query definitions
# ---------------------------------------------------------------------------

ASSOCIATIONS_QUERY = """
query TargetAssociations($target: String!) {
  target(ensemblId: $target) {
    id
    approvedSymbol
    approvedName
    biotype
    tractability { label modality value }
    associatedDiseases(page: { index: 0, size: 10 }) {
      rows {
        disease { name id }
        score
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""

KNOWN_DRUGS_QUERY = """
query KnownDrugs($target: String!) {
  target(ensemblId: $target) {
    knownDrugs(size: 20) {
      rows {
        drug { name maximumClinicalTrialPhase }
        phase
        status
        mechanismOfAction
        disease { name }
      }
    }
  }
}
"""

PATHWAYS_QUERY = """
query Pathways($target: String!) {
  target(ensemblId: $target) {
    pathways {
      pathway
      pathwayId
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Helper: resolve gene symbol → Ensembl ID
# ---------------------------------------------------------------------------

SEARCH_QUERY = """
query Search($q: String!, $entity: [String!]!) {
  search(queryString: $q, entityNames: $entity, page: { index: 0, size: 1 }) {
    hits {
      id
      entity
      name
    }
  }
}
"""

# Fetches the association score for a specific target filtered to a disease name.
# BFilter is Open Targets' text-search argument on associatedDiseases — we use the
# canonical OT disease name so the first result is almost always the right one.
DISEASE_SCORE_QUERY = """
query DiseaseScore($target: String!, $diseaseFilter: String!) {
  target(ensemblId: $target) {
    associatedDiseases(BFilter: $diseaseFilter, page: { index: 0, size: 10 }) {
      rows {
        disease { name id }
        score
      }
    }
  }
}
"""


def resolve_target_id(gene_symbol: str, client) -> str | None:
    """Convert gene symbol like 'KRAS' to Open Targets Ensembl ID."""
    resp = client.post(OPENTARGETS_URL, json={
        "query": SEARCH_QUERY,
        "variables": {"q": gene_symbol, "entity": ["target"]}
    })
    data = resp.json()
    hits = data.get("data", {}).get("search", {}).get("hits", [])
    if hits:
        return hits[0]["id"]
    return None


def resolve_disease_id(disease_name: str, client) -> tuple[str | None, str | None]:
    """
    Convert disease name to Open Targets EFO/MONDO ID and canonical name.
    Returns (efo_id, canonical_name) or (None, None) on failure.
    """
    resp = client.post(OPENTARGETS_URL, json={
        "query": SEARCH_QUERY,
        "variables": {"q": disease_name, "entity": ["disease"]}
    })
    data = resp.json()
    hits = data.get("data", {}).get("search", {}).get("hits", [])
    if hits:
        return hits[0]["id"], hits[0]["name"]
    return None, None


# ---------------------------------------------------------------------------
# Main worker function
# ---------------------------------------------------------------------------

def fetch_open_targets(target: str, disease: str) -> OpenTargetsResult:
    """
    Fetch genetic associations, known drugs, tractability, and pathways
    for a target-disease pair from Open Targets Platform.

    Args:
        target:  Gene/protein name, e.g. "KRAS"
        disease: Disease name, e.g. "non-small cell lung cancer"

    Returns:
        OpenTargetsResult with all fields populated (or defaults on failure)
    """
    start = time.time()

    try:
        import httpx
        with httpx.Client(timeout=30) as client:

            # Step 1: resolve gene symbol to Ensembl ID
            ensembl_id = resolve_target_id(target, client)
            if not ensembl_id:
                return OpenTargetsResult(
                    meta=WorkerMeta(
                        status=WorkerStatus.FAILED,
                        query_time_ms=int((time.time() - start) * 1000),
                        error=f"Could not resolve '{target}' to an Ensembl ID"
                    )
                )

            # Step 2: resolve disease to EFO ID + canonical name (for disease-specific scoring)
            disease_efo_id, disease_canonical_name = resolve_disease_id(disease, client)

            # Step 3: fetch associations + tractability
            assoc_resp = client.post(OPENTARGETS_URL, json={
                "query": ASSOCIATIONS_QUERY,
                "variables": {"target": ensembl_id}
            })
            assoc_data = assoc_resp.json().get("data", {}).get("target", {})

            # Parse genetic associations (top 10 by score, for context)
            associations = []
            rows = assoc_data.get("associatedDiseases", {}).get("rows", [])
            for row in rows:
                associations.append(GeneticAssociation(
                    study_id=row["disease"]["id"],
                    trait=row["disease"]["name"],
                    score=row["score"],
                    source="Open Targets"
                ))

            # Compute disease-specific genetic score:
            # 1. If we resolved the disease EFO ID, search for the exact match via BFilter.
            #    BFilter narrows the query to associations matching the disease name, then we
            #    pin to the exact EFO ID so pleiotropy in the BFilter results doesn't mislead.
            # 2. Fall back to max of top-10 only if disease resolution failed entirely.
            overall_score = 0.0
            if disease_efo_id and disease_canonical_name:
                score_resp = client.post(OPENTARGETS_URL, json={
                    "query": DISEASE_SCORE_QUERY,
                    "variables": {
                        "target": ensembl_id,
                        "diseaseFilter": disease_canonical_name,
                    }
                })
                score_rows = (
                    score_resp.json()
                    .get("data", {}).get("target", {})
                    .get("associatedDiseases", {}).get("rows", [])
                )
                for row in score_rows:
                    if row["disease"]["id"] == disease_efo_id:
                        overall_score = row["score"]
                        break
                # If queried disease wasn't found at all — score stays 0.0, which is correct:
                # the target has no genetic association with this specific disease in Open Targets.
            else:
                # Disease resolution failed — fall back to global max with caveat
                overall_score = max((a.score for a in associations), default=0.0)

            # Parse tractability — v4 API returns list of {label, modality, value}
            # modality: "SM" = small molecule, "AB" = antibody, "PR" = PROTAC
            tractability_label_scores = {
                "Approved Drug":                          1.0,
                "Advanced Clinical":                      0.8,
                "Phase 1 Clinical":                       0.6,
                "Predicted Tractable High Confidence":    0.4,
                "Predicted Tractable Med-Low Confidence": 0.2,
            }
            sm_score = 0.0
            ab_score = 0.0
            for item in (assoc_data.get("tractability") or []):
                if item.get("value"):
                    val = tractability_label_scores.get(item.get("label", ""), 0.0)
                    if item.get("modality") == "SM":
                        sm_score = max(sm_score, val)
                    elif item.get("modality") in ("AB", "PR"):
                        ab_score = max(ab_score, val)
            tractability_score = max(sm_score, ab_score)

            # Determine molecule type (biologic if antibody tractability > small mol)
            molecule_type = "biologic" if ab_score > sm_score else "small_molecule"

            # Step 4: fetch known drugs
            drugs_resp = client.post(OPENTARGETS_URL, json={
                "query": KNOWN_DRUGS_QUERY,
                "variables": {"target": ensembl_id}
            })
            drugs_data = drugs_resp.json().get("data", {}).get("target", {})
            known_drugs = []
            for row in (drugs_data.get("knownDrugs", {}) or {}).get("rows", [])[:OPENTARGETS_MAX_DRUGS]:
                known_drugs.append(KnownDrug(
                    drug_name=row["drug"]["name"],
                    phase=row.get("phase") or 0,
                    status=row.get("status") or "Unknown",
                    mechanism=row.get("mechanismOfAction") or "Unknown"
                ))

            # Step 5: fetch pathways
            path_resp = client.post(OPENTARGETS_URL, json={
                "query": PATHWAYS_QUERY,
                "variables": {"target": ensembl_id}
            })
            path_data = path_resp.json().get("data", {}).get("target", {})
            pathways = [p["pathway"] for p in (path_data.get("pathways") or [])[:10]]

            elapsed = int((time.time() - start) * 1000)
            return OpenTargetsResult(
                genetic_score=overall_score,
                genetic_associations=associations,
                known_drugs=known_drugs,
                pathways=pathways,
                tractability_score=tractability_score,
                molecule_type=molecule_type,
                meta=WorkerMeta(status=WorkerStatus.SUCCESS, query_time_ms=elapsed)
            )

    except Exception as e:
        return OpenTargetsResult(
            meta=WorkerMeta(
                status=WorkerStatus.FAILED,
                query_time_ms=int((time.time() - start) * 1000),
                error=str(e)
            )
        )

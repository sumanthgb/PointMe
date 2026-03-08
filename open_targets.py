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
query TargetDiseaseAssociations($target: String!, $disease: String!) {
  target(ensemblId: $target) {
    id
    approvedSymbol
    approvedName
    biotype
    tractability {
      smallMolecule { topCategory }
      antibody { topCategory }
    }
    associatedDiseases(filter: { name: $disease }, page: { size: 10 }) {
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
query Search($q: String!) {
  search(queryString: $q, entityNames: ["target"], page: { index: 0, size: 1 }) {
    hits {
      id
      entity
      name
    }
  }
}
"""

def resolve_target_id(gene_symbol: str, client) -> str | None:
    """Convert gene symbol like 'KRAS' to Open Targets Ensembl ID."""
    resp = client.post(OPENTARGETS_URL, json={
        "query": SEARCH_QUERY,
        "variables": {"q": gene_symbol}
    })
    data = resp.json()
    hits = data.get("data", {}).get("search", {}).get("hits", [])
    if hits:
        return hits[0]["id"]
    return None


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

            # Step 2: fetch associations + tractability
            assoc_resp = client.post(OPENTARGETS_URL, json={
                "query": ASSOCIATIONS_QUERY,
                "variables": {"target": ensembl_id, "disease": disease}
            })
            assoc_data = assoc_resp.json().get("data", {}).get("target", {})

            # Parse genetic associations
            associations = []
            overall_score = 0.0
            rows = assoc_data.get("associatedDiseases", {}).get("rows", [])
            for row in rows:
                associations.append(GeneticAssociation(
                    study_id=row["disease"]["id"],
                    trait=row["disease"]["name"],
                    score=row["score"],
                    source="Open Targets"
                ))
            if associations:
                overall_score = max(a.score for a in associations)

            # Parse tractability
            tractability = assoc_data.get("tractability", {})
            sm = tractability.get("smallMolecule", {}) or {}
            ab = tractability.get("antibody", {}) or {}
            # Score: "Clinical Precedence" > "Discovery Precedence" > "Predicted Tractable"
            tractability_map = {
                "Clinical Precedence": 1.0,
                "Discovery Precedence": 0.7,
                "Predicted Tractable High Confidence": 0.5,
                "Predicted Tractable Med-Low Confidence": 0.3,
            }
            sm_score = tractability_map.get(sm.get("topCategory", ""), 0.0)
            ab_score = tractability_map.get(ab.get("topCategory", ""), 0.0)
            tractability_score = max(sm_score, ab_score)

            # Determine molecule type (biologic if antibody tractability > small mol)
            molecule_type = "biologic" if ab_score > sm_score else "small_molecule"

            # Step 3: fetch known drugs
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

            # Step 4: fetch pathways
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

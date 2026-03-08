"""
workers/uniprot.py — Worker 4: UniProt REST API

API: https://rest.uniprot.org/uniprotkb/search
Fetches protein function, subcellular location, tissue expression, and disease associations.
Tissue expression data is the KEY input to the cross-reference engine's safety flag checks.
"""

import time
# httpx imported lazily inside functions (avoids import errors in test environments)
from models import UniProtResult, TissueExpression, WorkerMeta, WorkerStatus

BASE_URL = "https://rest.uniprot.org/uniprotkb/search"

# Expression level string → numeric mapping (for scoring)
EXPRESSION_LEVEL_MAP = {
    "High":         1.0,
    "Medium":       0.6,
    "Low":          0.3,
    "Not detected": 0.0,
}

# Fields to request from UniProt (v2 REST API field names)
FIELDS = ",".join([
    "accession",
    "gene_names",
    "protein_name",
    "cc_function",
    "cc_subcellular_location",
    "cc_tissue_specificity",
    "cc_disease",
])


def _parse_expression(comments: list[dict]) -> list[TissueExpression]:
    """
    Parse UniProt tissue specificity comments into TissueExpression list.
    UniProt encodes this as free-text comments — we do keyword extraction.
    """
    expressions = []
    for comment in comments:
        if comment.get("commentType") != "TISSUE SPECIFICITY":
            continue
        texts = comment.get("texts", [])
        for text_obj in texts:
            value = text_obj.get("value", "")
            # Simple heuristic: split on periods and semicolons, look for tissue + level
            for level in ["High", "Medium", "Low", "Not detected"]:
                if level.lower() in value.lower():
                    # Try to extract tissue name — look for patterns like "Highly expressed in X"
                    # This is a rough parse; for production use a NLP approach
                    import re
                    patterns = [
                        rf"(?:expressed|expression)\s+in\s+([a-zA-Z\s]+?)(?:\.|;|,|$)",
                        rf"([a-zA-Z\s]+?)\s+(?:express|shows?\s+{level})",
                    ]
                    for pat in patterns:
                        matches = re.findall(pat, value, re.IGNORECASE)
                        for match in matches[:3]:  # cap at 3 per comment
                            tissue = match.strip().lower()
                            if len(tissue) > 2:
                                expressions.append(TissueExpression(
                                    tissue=tissue,
                                    level=level,
                                    level_numeric=EXPRESSION_LEVEL_MAP.get(level, 0.0)
                                ))
    return expressions


def _parse_diseases(comments: list[dict]) -> list[str]:
    """Extract disease association names from UniProt comments."""
    diseases = []
    for comment in comments:
        if comment.get("commentType") != "DISEASE":
            continue
        disease = comment.get("disease", {})
        name = disease.get("diseaseId") or disease.get("acronym")
        if name:
            diseases.append(name)
    return diseases


def fetch_uniprot(target: str, disease: str) -> UniProtResult:
    """
    Fetch protein data from UniProt for a given gene/target name.

    Args:
        target:  Gene or protein name, e.g. "KRAS" or "KRAS G12C"
        disease: Not directly used in query but kept for interface consistency

    Returns:
        UniProtResult with expression, function, location, and disease data.
    """
    start = time.time()

    # Normalise: extract base gene name (e.g. "KRAS G12C" → "KRAS")
    gene_name = target.split()[0].upper()

    try:
        import httpx
        with httpx.Client(timeout=30) as client:
            resp = client.get(BASE_URL, params={
                "query": f"gene:{gene_name} AND organism_id:9606 AND reviewed:true",  # reviewed:true = Swiss-Prot canonical entry
                "format": "json",
                "fields": FIELDS,
                "size": 1,  # take the top canonical human entry
            })
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return UniProtResult(
                meta=WorkerMeta(
                    status=WorkerStatus.PARTIAL,
                    query_time_ms=int((time.time() - start) * 1000),
                    error=f"No UniProt entry found for gene '{gene_name}'"
                )
            )

        entry = results[0]
        accession = entry.get("primaryAccession", "")
        comments = entry.get("comments", [])
        genes = entry.get("genes", [{}])
        gene_names_raw = genes[0].get("geneName", {}).get("value", gene_name) if genes else gene_name

        # Function
        function_comments = [c for c in comments if c.get("commentType") == "FUNCTION"]
        function_summary = ""
        if function_comments:
            texts = function_comments[0].get("texts", [])
            function_summary = texts[0].get("value", "") if texts else ""

        # Subcellular location
        loc_comments = [c for c in comments if c.get("commentType") == "SUBCELLULAR LOCATION"]
        subcellular_locations = []
        for loc_comment in loc_comments:
            for loc in loc_comment.get("subcellularLocations", []):
                loc_name = loc.get("location", {}).get("value")
                if loc_name:
                    subcellular_locations.append(loc_name)

        # Tissue expression
        tissue_expression = _parse_expression(comments)

        # Disease associations
        disease_associations = _parse_diseases(comments)

        elapsed = int((time.time() - start) * 1000)
        return UniProtResult(
            uniprot_id=accession,
            gene_name=gene_names_raw,
            function_summary=function_summary[:500],
            subcellular_location=subcellular_locations,
            tissue_expression=tissue_expression,
            disease_associations=disease_associations,
            meta=WorkerMeta(status=WorkerStatus.SUCCESS, query_time_ms=elapsed)
        )

    except Exception as e:
        return UniProtResult(
            meta=WorkerMeta(
                status=WorkerStatus.FAILED,
                query_time_ms=int((time.time() - start) * 1000),
                error=str(e)
            )
        )

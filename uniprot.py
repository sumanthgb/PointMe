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
    
    UniProt encodes this as free-text like:
      "Expressed at high levels in the brain and pancreas."
      "Widely expressed. Highest expression in liver and kidney."
    
    Strategy: split on sentences, find tissue keywords, infer level from context.
    """
    import re

    # Known tissues/organs to scan for
    KNOWN_TISSUES = [
        "brain", "liver", "kidney", "heart", "lung", "pancreas", "spleen",
        "intestine", "colon", "stomach", "skin", "bone marrow", "thymus",
        "lymph node", "testis", "ovary", "uterus", "prostate", "breast",
        "muscle", "skeletal muscle", "adipose", "adrenal", "thyroid",
        "pituitary", "placenta", "retina", "cornea", "blood", "plasma",
        "serum", "platelet", "leukocyte", "lymphocyte", "monocyte",
        "neutrophil", "macrophage", "fibroblast", "endothelial",
        "substantia nigra", "hippocampus", "cortex", "cerebellum",
        "spinal cord", "trachea", "esophagus", "bladder", "eye",
        "salivary gland", "gallbladder", "small intestine", "appendix",
        "bone", "cartilage", "nerve", "dorsal root ganglia",
        "locus coeruleus", "medulla oblongata",
    ]

    # Words that indicate expression level
    HIGH_WORDS = {"high", "highest", "highly", "strongly", "predominantly", "abundant", "abundantly", "enriched", "ubiquitous", "ubiquitously", "widely"}
    LOW_WORDS = {"low", "lowest", "weakly", "faint", "faintly", "barely", "minor", "trace"}
    MEDIUM_WORDS = {"moderate", "moderately", "intermediate"}
    NOT_DETECTED_WORDS = {"not detected", "absent", "undetectable", "not expressed", "no expression"}

    expressions = []
    seen_tissues: set[str] = set()

    for comment in comments:
        if comment.get("commentType") != "TISSUE SPECIFICITY":
            continue
        texts = comment.get("texts", [])
        for text_obj in texts:
            value = text_obj.get("value", "")
            if not value:
                continue

            value_lower = value.lower()

            # Determine the "default" level for the whole block
            # e.g. "Expressed at high levels in the brain and pancreas" → default is High
            default_level = "Medium"  # fallback
            if any(w in value_lower for w in NOT_DETECTED_WORDS):
                default_level = "Not detected"
            elif any(w in value_lower for w in HIGH_WORDS):
                default_level = "High"
            elif any(w in value_lower for w in LOW_WORDS):
                default_level = "Low"
            elif any(w in value_lower for w in MEDIUM_WORDS):
                default_level = "Medium"

            # Split into sentences for finer-grained analysis
            sentences = re.split(r'[.;]', value)

            for sentence in sentences:
                sentence_lower = sentence.lower().strip()
                if not sentence_lower:
                    continue

                # Determine sentence-level expression level
                sent_level = default_level
                if any(w in sentence_lower for w in NOT_DETECTED_WORDS):
                    sent_level = "Not detected"
                elif any(w in sentence_lower for w in HIGH_WORDS):
                    sent_level = "High"
                elif any(w in sentence_lower for w in LOW_WORDS):
                    sent_level = "Low"
                elif any(w in sentence_lower for w in MEDIUM_WORDS):
                    sent_level = "Medium"

                # Find all tissue mentions in this sentence
                for tissue in KNOWN_TISSUES:
                    if tissue in sentence_lower and tissue not in seen_tissues:
                        seen_tissues.add(tissue)
                        expressions.append(TissueExpression(
                            tissue=tissue,
                            level=sent_level,
                            level_numeric=EXPRESSION_LEVEL_MAP.get(sent_level, 0.0)
                        ))

            # If text mentions "widely expressed" or "ubiquitous" but we found no specific tissues,
            # add a generic "ubiquitous" entry
            if not expressions and ("widely" in value_lower or "ubiquitous" in value_lower):
                expressions.append(TissueExpression(
                    tissue="ubiquitous",
                    level="Medium",
                    level_numeric=0.6
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


def _fetch_hpa_expression(gene_name: str) -> list[TissueExpression]:
    """
    Fallback: fetch tissue RNA expression from Human Protein Atlas.
    Returns TissueExpression list based on nTPM values.
    
    HPA levels:  nTPM >= 20 → High,  5-20 → Medium,  1-5 → Low,  <1 → Not detected
    """
    import urllib.request
    import urllib.parse
    import json
    
    # Key safety-relevant tissues
    HPA_TISSUES = [
        "brain", "liver", "kidney", "lung", "heart+muscle",
        "pancreas", "colon", "stomach", "skin", "bone+marrow",
        "spleen", "testis", "thyroid", "adrenal+gland",
    ]
    
    columns = "g," + ",".join(f"t_RNA_{t}" for t in HPA_TISSUES)
    
    try:
        params = urllib.parse.urlencode({
            "search": gene_name,
            "format": "json",
            "columns": columns,
            "compress": "no",
        })
        url = f"https://www.proteinatlas.org/api/search_download.php?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
    except Exception:
        return []
    
    if not data:
        return []
    
    entry = data[0]
    expressions = []
    
    for key, value in entry.items():
        if key == "Gene" or not value:
            continue
        # Key format: "Tissue RNA - liver [nTPM]"
        tissue_name = key.replace("Tissue RNA - ", "").replace(" [nTPM]", "").replace("+", " ").strip().lower()
        
        try:
            ntpm = float(value)
        except (ValueError, TypeError):
            continue
        
        if ntpm >= 20:
            level = "High"
        elif ntpm >= 5:
            level = "Medium"
        elif ntpm >= 1:
            level = "Low"
        else:
            level = "Not detected"
        
        expressions.append(TissueExpression(
            tissue=tissue_name,
            level=level,
            level_numeric=EXPRESSION_LEVEL_MAP.get(level, 0.0)
        ))
    
    return expressions


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

        # Supplement with Human Protein Atlas data to fill tissue gaps.
        # If UniProt returned 0 tissues, HPA becomes the primary source.
        # If UniProt returned some, HPA fills in missing tissues (e.g. BACE1 liver).
        try:
            hpa_tissues = _fetch_hpa_expression(gene_name)
            if hpa_tissues:
                existing_names = {t.tissue for t in tissue_expression}
                for hpa_t in hpa_tissues:
                    if hpa_t.tissue not in existing_names:
                        tissue_expression.append(hpa_t)
        except Exception:
            pass  # HPA is best-effort

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

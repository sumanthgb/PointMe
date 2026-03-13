"""
test_workers.py — Standalone test harness for PointMe API workers.

Usage:
    python test_workers.py                  # Run all tests
    python test_workers.py open_targets     # Run one worker test
    python test_workers.py uniprot          # etc.

Each test calls the worker function directly with a known target-disease pair
and checks the output against ground-truth expected values from Claude's oracle.
"""

import sys
import json
import time

# ── Ground-truth oracle data ────────────────────────────────────────────────

BACE1 = {
    "target": "BACE1",
    "disease": "Alzheimer's disease",
    "ensembl_id": "ENSG00000186318",
    "uniprot_id": "P56817",
    "genetic_score_range": (0.15, 0.50),   # moderate-low
    "molecule_type": "small_molecule",
    "expected_failed_ncts": [
        "NCT01739348",  # verubecestat EPOCH
        "NCT01953601",  # verubecestat APECS
        "NCT02245737",  # lanabecestat AMARANTH
        "NCT02783573",  # lanabecestat DAYBREAK-ALZ
        "NCT02569398",  # atabecestat EARLY
        "NCT01561430",  # LY2886721
        "NCT02956486",  # elenbecestat MissionAD1
    ],
    "expected_known_drugs": ["VERUBECESTAT", "LANABECESTAT", "ATABECESTAT", "ELENBECESTAT"],
    "expected_expression": {"brain": "High", "liver": "Low"},  # at minimum
    "expected_fda_approved_for_target": 0,  # no BACE1 drugs approved
    "prevalence_us": 6_900_000,
    "verdict": "NO-GO",
}

KRAS = {
    "target": "KRAS G12C",
    "disease": "non-small cell lung cancer",
    "ensembl_id": "ENSG00000133703",
    "uniprot_id": "P01116",
    "genetic_score_range": (0.50, 1.0),    # high
    "molecule_type": "small_molecule",
    "expected_success_ncts": [
        "NCT03600883",  # sotorasib CodeBreaK 100
        "NCT04303780",  # sotorasib CodeBreaK 200
        "NCT03785249",  # adagrasib KRYSTAL-1
    ],
    "expected_known_drugs": ["SOTORASIB", "ADAGRASIB"],
    "expected_expression": {},  # KRAS is ubiquitous, less specific
    "expected_fda_approved_for_target": 2,  # sotorasib + adagrasib
    "prevalence_us": 234_000,
    "verdict": "GO",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

import os as _os
_COLORS = _os.name != "nt"  # disable colors on Windows

GREEN  = "\033[92m" if _COLORS else ""
RED    = "\033[91m" if _COLORS else ""
YELLOW = "\033[93m" if _COLORS else ""
RESET  = "\033[0m"  if _COLORS else ""
BOLD   = "\033[1m"  if _COLORS else ""

def ok(msg):   print(f"  [OK] {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def warn(msg): print(f"  [WARN] {msg}")

def header(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

def sub(name):
    print(f"\n  -- {name} --")


# ── Test: Open Targets ──────────────────────────────────────────────────────

def test_open_targets():
    header("Worker 1: Open Targets")
    from open_targets import fetch_open_targets

    for case in [BACE1, KRAS]:
        sub(f"{case['target']} / {case['disease']}")
        t0 = time.time()
        result = fetch_open_targets(case["target"], case["disease"])
        elapsed = int((time.time() - t0) * 1000)

        print(f"  Status: {result.meta.status.value} ({elapsed}ms)")
        if result.meta.error:
            fail(f"Error: {result.meta.error}")
            continue

        # Genetic score
        lo, hi = case["genetic_score_range"]
        score = result.genetic_score
        if lo <= score <= hi:
            ok(f"Genetic score: {score:.3f} (expected {lo}-{hi})")
        else:
            warn(f"Genetic score: {score:.3f} (expected {lo}-{hi})")

        # Molecule type
        if result.molecule_type == case["molecule_type"]:
            ok(f"Molecule type: {result.molecule_type}")
        else:
            warn(f"Molecule type: {result.molecule_type} (expected {case['molecule_type']})")

        # Known drugs
        drug_names = [d.drug_name.upper() for d in result.known_drugs]
        found = [d for d in case["expected_known_drugs"] if d in drug_names]
        if found:
            ok(f"Known drugs found: {', '.join(found)} ({len(result.known_drugs)} total)")
        else:
            warn(f"Known drugs: {drug_names[:5]} — expected {case['expected_known_drugs']}")

        # Tractability
        print(f"  Tractability: {result.tractability_score:.2f}")
        print(f"  Pathways: {result.pathways[:3]}")
        print(f"  Associations: {len(result.genetic_associations)}")


# ── Test: ClinicalTrials.gov ─────────────────────────────────────────────────

def test_clinical_trials():
    header("Worker 2: ClinicalTrials.gov")
    from clinical_trials import fetch_clinical_trials

    for case in [BACE1, KRAS]:
        sub(f"{case['target']} / {case['disease']}")
        t0 = time.time()
        result = fetch_clinical_trials(case["target"], case["disease"])
        elapsed = int((time.time() - t0) * 1000)

        print(f"  Status: {result.meta.status.value} ({elapsed}ms)")
        if result.meta.error:
            fail(f"Error: {result.meta.error}")
            continue

        print(f"  Active: {len(result.active_trials)}, Completed: {len(result.completed_trials)}, Failed: {len(result.failed_trials)}")
        print(f"  Success rate: {result.success_rate:.2f}")
        print(f"  Phases: {result.phases}")

        # Check for expected failed trials (BACE1)
        if "expected_failed_ncts" in case:
            failed_ids = {t.nct_id for t in result.failed_trials}
            found = [nct for nct in case["expected_failed_ncts"] if nct in failed_ids]
            if found:
                ok(f"Found {len(found)}/{len(case['expected_failed_ncts'])} expected failed trials")
            else:
                warn(f"No expected failed trials found. Got: {list(failed_ids)[:5]}")

            # Print why_stopped for failed trials
            for t in result.failed_trials[:5]:
                reason = t.why_stopped or "not specified"
                print(f"    {t.nct_id} [{t.phase or '?'}] — {reason[:80]}")

        # Check for expected successful trials (KRAS)
        if "expected_success_ncts" in case:
            all_ids = {t.nct_id for t in result.active_trials + result.completed_trials}
            found = [nct for nct in case["expected_success_ncts"] if nct in all_ids]
            if found:
                ok(f"Found {len(found)}/{len(case['expected_success_ncts'])} expected successful trials")
            else:
                warn(f"Expected successful trials not in results. Got: {list(all_ids)[:5]}")


# ── Test: PubMed ─────────────────────────────────────────────────────────────

def test_pubmed():
    header("Worker 3: PubMed")
    from pubmed import fetch_pubmed

    for case in [BACE1, KRAS]:
        sub(f"{case['target']} / {case['disease']}")
        t0 = time.time()
        result = fetch_pubmed(case["target"], case["disease"])
        elapsed = int((time.time() - t0) * 1000)

        print(f"  Status: {result.meta.status.value} ({elapsed}ms)")
        if result.meta.error:
            warn(f"Note: {result.meta.error}")

        print(f"  Total papers: {result.total_papers}")
        print(f"  Relevance score: {result.relevance_score:.3f}")

        if result.total_papers > 100:
            ok(f"Substantial literature found ({result.total_papers} papers)")
        else:
            warn(f"Low paper count ({result.total_papers})")

        for p in result.papers[:3]:
            safe_title = p.title[:70].encode('ascii', 'replace').decode('ascii')
            print(f"    [{p.year}] {safe_title}... ({p.journal or 'unknown journal'})")


# ── Test: UniProt ────────────────────────────────────────────────────────────

def test_uniprot():
    header("Worker 4: UniProt")
    from uniprot import fetch_uniprot

    for case in [BACE1, KRAS]:
        sub(f"{case['target']} / {case['disease']}")
        t0 = time.time()
        result = fetch_uniprot(case["target"], case["disease"])
        elapsed = int((time.time() - t0) * 1000)

        print(f"  Status: {result.meta.status.value} ({elapsed}ms)")
        if result.meta.error:
            warn(f"Note: {result.meta.error}")

        # UniProt ID
        if result.uniprot_id == case["uniprot_id"]:
            ok(f"UniProt ID: {result.uniprot_id}")
        elif result.uniprot_id:
            warn(f"UniProt ID: {result.uniprot_id} (expected {case['uniprot_id']})")
        else:
            fail(f"UniProt ID: None (expected {case['uniprot_id']})")

        print(f"  Gene: {result.gene_name}")
        print(f"  Function: {result.function_summary[:100]}...")
        print(f"  Location: {result.subcellular_location}")
        print(f"  Diseases: {result.disease_associations[:3]}")

        # Tissue expression — this is the critical check
        print(f"  Tissue expression ({len(result.tissue_expression)} entries):")
        if result.tissue_expression:
            for te in result.tissue_expression:
                print(f"    {te.tissue}: {te.level} ({te.level_numeric})")
            ok("Expression data found")
        else:
            fail("NO expression data — cross-reference safety flags will not work!")

        # Check expected organs
        for organ, expected_level in case.get("expected_expression", {}).items():
            found = [te for te in result.tissue_expression if organ in te.tissue.lower()]
            if found:
                ok(f"Found {organ} expression: {found[0].level}")
            else:
                fail(f"Missing {organ} expression (expected {expected_level})")


# ── Test: FDA Drugs ──────────────────────────────────────────────────────────

def test_fda_drugs():
    header("Worker 5: Drugs@FDA")
    from fda_drugs import fetch_fda_drugs

    for case in [BACE1, KRAS]:
        sub(f"{case['target']} / {case['disease']}")
        t0 = time.time()
        result = fetch_fda_drugs(case["target"], case["disease"])
        elapsed = int((time.time() - t0) * 1000)

        print(f"  Status: {result.meta.status.value} ({elapsed}ms)")
        if result.meta.error:
            warn(f"Note: {result.meta.error}")

        print(f"  Approved drugs: {len(result.approved_drugs)}")
        for d in result.approved_drugs[:5]:
            print(f"    {d.name} — {d.pathway} ({d.application_type})")

        print(f"  Rejected drugs: {len(result.rejected_drugs)}")
        print(f"  Same-MOA drugs: {len(result.approved_drugs_same_moa)}")


# ── Test: Orange Book ────────────────────────────────────────────────────────

def test_orange_book():
    header("Worker 6: Orange Book")
    from orange_book import fetch_orange_book

    for case in [BACE1, KRAS]:
        sub(f"{case['target']} / {case['disease']}")
        t0 = time.time()
        result = fetch_orange_book(case["target"], case["disease"])
        elapsed = int((time.time() - t0) * 1000)

        print(f"  Status: {result.meta.status.value} ({elapsed}ms)")
        if result.meta.error:
            warn(f"Note: {result.meta.error}")

        print(f"  Comparable drugs: {len(result.comparable_drugs)}")
        for d in result.comparable_drugs[:5]:
            print(f"    {d.name} (excl: {d.exclusivity_type}, patent: {d.patent_number})")
        print(f"  IP crowding score: {result.ip_crowding_score:.2f}")


# ── Runner ───────────────────────────────────────────────────────────────────

TESTS = {
    "open_targets":    test_open_targets,
    "clinical_trials": test_clinical_trials,
    "pubmed":          test_pubmed,
    "uniprot":         test_uniprot,
    "fda_drugs":       test_fda_drugs,
    "orange_book":     test_orange_book,
}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        name = sys.argv[1]
        if name in TESTS:
            TESTS[name]()
        else:
            print(f"Unknown test: {name}")
            print(f"Available: {', '.join(TESTS.keys())}")
    else:
        for test_fn in TESTS.values():
            try:
                test_fn()
            except Exception as e:
                print(f"  {RED}ERROR: {e}{RESET}")
        print(f"\n{BOLD}Done.{RESET}")

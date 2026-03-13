# PointMe Backend — Bug Fix Summary
**Date:** March 12, 2026  
**Fixed by:** Aparna (with AI assistance)

---

## What Happened

During the hackathon demo, the website showed wrong/missing information because several backend API workers had bugs. Here's what was broken and how we fixed each one.

---

## Bug 1: ClinicalTrials.gov — Blocked by Server (403 Forbidden)

**Symptom:** Zero clinical trials returned for any query.  
**Root cause:** The `httpx` Python library was being identified and blocked by ClinicalTrials.gov's server.  
**Fix:** Replaced `httpx` with Python's built-in `urllib.request` + a browser-like `User-Agent` header.  
**File:** `clinical_trials.py`  
**Result:** BACE1 → 16 completed + 10 failed trials. KRAS → 69 active + 15 completed + 16 failed trials.

---

## Bug 2: PubMed — Unicode Crash on Windows

**Symptom:** Test script crashed with `UnicodeEncodeError` when printing paper titles with Greek characters (β, α).  
**Root cause:** Windows PowerShell uses cp1252 encoding which can't render Unicode characters.  
**Fix:** Added ASCII-safe encoding before printing.  
**File:** `test_workers.py`  
**Result:** No more crashes. 3,058 papers for BACE1, 537 for KRAS.

---

## Bug 3: UniProt — Zero Tissue Expression Data (CRITICAL)

This was the biggest bug. The tissue expression data feeds directly into safety flag generation.

**Symptom:** UniProt worker returned 0 tissues for every protein.  
**Root cause:** The expression parser used regex patterns that expected text like `"Highly expressed in brain"`, but real UniProt text says `"Expressed at high levels in the brain and pancreas"`. The regex never matched.  
**Fix (2 parts):**
1. **Rewrote the parser** — scans for 50+ known tissue keywords (brain, liver, kidney, etc.) and infers expression level from context words
2. **Added Human Protein Atlas (HPA) fallback** — for genes like KRAS that have no tissue data in UniProt, queries HPA API for RNA expression values (nTPM) and converts to High/Medium/Low

**Files:** `uniprot.py`  
**Result:** BACE1 → 10 tissues (brain=High, liver=High, pancreas=High, etc.). KRAS → 7 tissues via HPA.

---

## Bug 4: FDA Drugs & Orange Book — Searching by Gene Name

**Symptom:** Zero drugs found for any target.  
**Root cause:** Code searched openFDA for `active_ingredients.name:"kras"`, but "KRAS" is a gene name — not a drug ingredient. The drugs are "SOTORASIB", "ADAGRASIB", etc.  
**Fix:** Added `supplement_with_drug_names()` functions. The orchestration layer (`app.py`) now takes drug names from Open Targets and feeds them into the FDA/Orange Book searches.  
**Files:** `fda_drugs.py`, `orange_book.py`, `app.py`  
**Result:** Both workers now find real FDA-approved drug data when run through the full pipeline.

---

## Verification Results

### BACE1 / Alzheimer's Disease (Expected: NO-GO)

| Data Point | Before Fix | After Fix |
|---|---|---|
| Genetic score | 0.354 ✅ | 0.354 ✅ |
| Clinical trials | ❌ 0 (403 error) | ✅ 16 completed, 10 failed |
| PubMed papers | ❌ crash | ✅ 3,058 papers |
| Tissue expressions | ❌ 0 | ✅ 10 (brain=High, liver=High) |
| Safety flags | ❌ 0 | ✅ 11 flags (including liver toxicity cross-ref!) |
| Known drugs | 15 ✅ | 15 ✅ |

**Key flag generated:** *"CRITICAL: Trial NCT02569398 failed due to liver toxicity AND target shows high liver expression. Two independent sources confirm this risk."*

### KRAS G12C / NSCLC (Expected: GO)

| Data Point | Before Fix | After Fix |
|---|---|---|
| Genetic score | 0.779 ✅ | 0.779 ✅ |
| Clinical trials | ❌ 0 (403 error) | ✅ 69 active, 15 completed, 16 failed |
| PubMed papers | ❌ crash | ✅ 537 papers |
| Tissue expressions | ❌ 0 | ✅ 7 (colon=High, liver/lung/kidney=Medium) |
| Safety flags | ❌ 0 | ✅ 5 flags |
| Known drugs | 20 ✅ | 20 ✅ |

---

## What's Working Now

- ✅ All 6 API workers return real data
- ✅ Cross-reference engine generates safety flags
- ✅ ClinicalTrials data feeds into trial analysis
- ✅ Tissue expression data enables toxicity flagging
- ✅ Full pipeline runs end-to-end in ~3-4 seconds

## Remaining Items

- **LLM Synthesis** — requires `ANTHROPIC_API_KEY` environment variable
- **Overall Score / Verdict** — shows N/A (likely needs LLM or scoring config)
- **Render cold-start mitigation** — cron job to ping health page (already done by Sumanth)

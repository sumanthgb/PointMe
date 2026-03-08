# PointMe — Backend

AI platform for evaluating drug targets on scientific merit AND regulatory feasibility simultaneously.

**Input:** target + disease pair (e.g. `KRAS G12C` + `non-small cell lung cancer`)  
**Output:** GO / CAUTION / NO-GO recommendation backed by 6 live data sources, a deterministic rules engine, contradiction detection, weighted scoring, and an LLM-generated assessment memo.

---

## Project Structure

```
PointMe/
├── app.py                ← FastAPI server — run this
├── models.py             ← Pydantic models (shared contract between all components)
├── config.py             ← All constants, thresholds, scoring weights
├── llm_synthesis.py      ← Claude API call (last step — explains results, doesn't decide)
├── mock_response.json    ← Mock JSON for frontend dev (no pipeline call needed)
├── requirements.txt
│
├── Data workers (run in parallel)
│   ├── open_targets.py   ← Worker 1: Open Targets GraphQL API
│   ├── clinical_trials.py← Worker 2: ClinicalTrials.gov v2 REST API
│   ├── pubmed.py         ← Worker 3: PubMed E-utilities
│   ├── uniprot.py        ← Worker 4: UniProt REST API
│   ├── fda_drugs.py      ← Worker 5: Drugs@FDA / openFDA
│   └── orange_book.py    ← Worker 6: FDA Orange Book
│
└── Engines (deterministic Python — no LLM)
    ├── regulatory.py     ← Regulatory rules engine (8 rules, full audit trail)
    ├── cross_reference.py← Contradiction detection (6 checks across all workers)
    └── scoring.py        ← Weighted evidence scoring algorithm
```

---

## Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Anthropic API key
export ANTHROPIC_API_KEY='sk-ant-your-key-here'

# 3. Start the server
uvicorn app:app --reload --port 8000
```

Server starts in ~2 seconds at `http://localhost:8000`.

---

## API Endpoints

### Health check
```bash
curl http://localhost:8000/health
```

### Mock response (for frontend dev — no pipeline call)
```bash
curl http://localhost:8000/mock
```
Send this URL to the frontend team: they can build against this without waiting for the full pipeline.

### Full evaluation
```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"target": "KRAS G12C", "disease": "non-small cell lung cancer"}'
```

### Interactive API docs
Open `http://localhost:8000/docs` in your browser — FastAPI generates this automatically.

---

## Public URL (for sharing / frontend integration)

```bash
# In a second terminal, after uvicorn is running:
ngrok http 8000
```

This gives a public `https://xxxx.ngrok.io` URL that proxies to your local server.

---

## Pipeline

```
POST /evaluate
    │
    ├── 6 data workers (concurrent, asyncio + ThreadPoolExecutor)
    │   ├── Open Targets   — genetic associations, tractability, known drugs
    │   ├── ClinicalTrials — active / completed / failed trials + why_stopped
    │   ├── PubMed         — paper volume + recency-weighted relevance score
    │   ├── UniProt        — tissue expression, function, subcellular location
    │   ├── Drugs@FDA      — approved/rejected drugs, approval pathway
    │   └── Orange Book    — comparable drugs, IP crowding score
    │
    ├── Regulatory rules engine (deterministic, 8 rules, full audit trail)
    │   └── → recommended pathway, special designations, timeline, cost
    │
    ├── Cross-reference engine (6 checks across worker outputs)
    │   └── → contradiction flags, safety flags, IP risk flags (sorted by severity)
    │
    ├── Scoring algorithm (weighted, 0-100)
    │   ├── Science score:    genetic 30% + literature 20% + clinical 25% + tractability 15% + safety 10%
    │   ├── Regulatory score: pathway 25% + designations 20% + competition 20% + precedent 20% + IP 15%
    │   └── Combined score:   science 50% + regulatory 50% → GO / CAUTION / NO-GO
    │
    └── LLM synthesis (Claude Sonnet — explains results, does NOT make decisions)
        └── → 5-section assessment memo
```

---

## Environment

Only one secret required:

| Variable | Required | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | platform.anthropic.com → API Keys |

All 6 data sources are free public APIs — no keys needed.

---

## Response Shape

```json
{
  "target": "KRAS G12C",
  "disease": "non-small cell lung cancer",
  "scores": {
    "science_score": 78.4,
    "regulatory_score": 61.2,
    "combined_score": 69.8,
    "recommendation": "GO"
  },
  "scientific_evidence": { ... },
  "regulatory_assessment": {
    "recommended_pathway": "505(b)(1)",
    "special_designations": ["fast_track", "breakthrough_therapy"],
    "estimated_timeline_years": "8-12 years",
    "estimated_cost_range": "$800M-2B",
    "reasoning": [ ... ]
  },
  "flags": [ ... ],
  "llm_synthesis": "1. EXECUTIVE SUMMARY\n...",
  "data_sources": {
    "open_targets":   { "status": "success", "query_time_ms": 412 },
    "clinicaltrials": { "status": "success", "query_time_ms": 634 },
    ...
  }
}
```

<<<<<<< HEAD
See `mock_response.json` for a full worked example with KRAS G12C / NSCLC.
======

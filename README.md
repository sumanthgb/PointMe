# TargetIQ — Backend

AI platform for evaluating drug targets on scientific merit AND regulatory feasibility.

## Project Structure

```
targetiq/
├── modal_app.py          ← Main Modal app: orchestrator + all 6 workers registered
├── orchestrator.py       ← Parallel fan-out logic, result aggregation
├── workers/
│   ├── open_targets.py   ← Worker 1: Open Targets GraphQL API
│   ├── clinical_trials.py← Worker 2: ClinicalTrials.gov REST API
│   ├── pubmed.py         ← Worker 3: PubMed E-utilities
│   ├── uniprot.py        ← Worker 4: UniProt REST API
│   ├── fda_drugs.py      ← Worker 5: Drugs@FDA / openFDA
│   └── orange_book.py    ← Worker 6: FDA Orange Book
├── engine/
│   ├── regulatory.py     ← Deterministic regulatory rules engine
│   ├── cross_reference.py← Contradiction detection engine
│   └── scoring.py        ← Weighted evidence scoring algorithm
├── api/
│   └── endpoint.py       ← FastAPI app served via Modal web endpoint
├── models.py             ← Pydantic models for all data shapes
├── config.py             ← Constants, thresholds, weights
└── mock_response.json    ← Mock JSON for Rithika's frontend build
```

## Quickstart

```bash
pip install modal anthropic fastapi httpx gql
modal setup          # authenticate with your Modal account
modal serve modal_app.py   # hot-reload dev server
modal deploy modal_app.py  # deploy to production
```

## Environment Secrets (set in Modal dashboard)
- `ANTHROPIC_API_KEY` — for LLM synthesis layer
- `OPENAI_API_KEY`    — backup/second opinion (optional)

## API Usage

```bash
curl -X POST https://your-modal-endpoint.modal.run/evaluate \
  -H "Content-Type: application/json" \
  -d '{"target": "KRAS G12C", "disease": "non-small cell lung cancer"}'
```

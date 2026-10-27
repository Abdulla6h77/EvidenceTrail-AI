# EvidenceTrail AI Demo Script

## Setup

```bash
cd backend
pip install -r requirements.txt
python -m app.data.seed
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

For a serverless terminal proof of the memory handoff, run this from the repository root:

```bash
python scripts/run_demo.py
```

## Three-minute walkthrough

### 1. Overview

Point out:

- total investigations and completed reports;
- Demo mode is explicit;
- Synthetic retail is ready without credentials;
- Zetaris, Nemotron, and H-MEM statuses are not misrepresented.

### 2. Investigation A — explain the decline

Submit:

> Why did sales decrease in September 2025?

Show the six stages completing:

1. question parsing;
2. safe plan construction;
3. actual data retrieval;
4. evidence evaluation;
5. contradictions and missing controls;
6. final report generation.

On the report, highlight:

- total revenue fell from August to September;
- Trail Running Shoes is a concentrated decline driver;
- September stockout days and Northstar supplier delay support an availability contribution;
- price/unit movement is an association, not a proven causal effect;
- missing promotion, competitor, and randomized-experiment data.

Open the SQL section to show query IDs, row counts, durations, and read-only statements.

### 3. Investigation B — demonstrate memory reuse

Submit:

> Are stockouts contributing to lost sales in September 2025?

Show the Memory trace banner:

- a prior memory ID was retrieved;
- retrieval influenced planning;
- an explicit “Memory-informed check” query was added.

This is the mandatory local proof that a stored evidence-backed summary changes a related follow-up investigation. It is not presented as a live Meterless service connection.

### 4. History and downloads

- Open Investigation history.
- Reopen either report.
- Download Markdown and JSON.
- Search by “stockouts” or “September”.

## Optional API proof

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/overview
curl -X POST http://localhost:8000/api/investigations \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did sales decrease in September 2025?","mode":"demo"}'
```

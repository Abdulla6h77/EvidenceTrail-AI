# EvidenceTrail AI

EvidenceTrail AI is an evidence-first investigation agent for explaining why a measurable business outcome changed. It is being built for the Open Agent Hackathon 2026, with a provisional focus on Track 2 — “The Agent That Can Explain Why”.

Demo mode runs without external credentials using synthetic retail data and read-only SQLite. Live mode executes SQL through Zetaris and generates an evidence-grounded synthesis with the configured Nemotron model. The running local application has the genuine Meterless reference engine enabled, with persistent memory and an audit ledger.

> **Synthetic data notice:** all retail events are generated for demonstration and testing. They do not represent real business events.

## What works in the MVP

- Submit natural-language questions such as “Why did sales decrease in September 2025?”
- Track six observable investigation stages without exposing hidden chain-of-thought.
- Execute safe, read-only SQL over a seeded retail SQLite database.
- Produce structured reports with findings, supporting/contradicting evidence, provenance, confidence, uncertainty, and recommended actions.
- Persist and search investigation history.
- Store investigation summaries in a working/long-term H-MEM-compatible local memory store and show when prior memory influenced a follow-up plan.
- Download report JSON or Markdown from the API and UI.
- Inspect Demo/Live connectivity status for the data source, model, and memory adapter.

## Repository layout

```text
.
├── backend/       FastAPI application, workflow, adapters, tests
├── frontend/      Next.js App Router dashboard
├── data/           generated sample-data artifacts and runtime database
├── docs/           implementation, architecture, demo and submission notes
└── scripts/        repeatable data/setup helpers
```

## Requirements

- Python 3.11+
- Node.js 20+
- npm 10+

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python -m app.data.seed
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`; OpenAPI docs are at `/docs`.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

If the API runs somewhere else, set only `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` before `npm run dev`; do not copy backend secrets into the frontend environment.

## Test and check commands

```bash
cd backend
python -m pytest -q

cd ../frontend
npm run lint
npm run build
```

The frontend currently has no browser automation dependency; the dashboard’s core flow is also covered through backend API tests and can be smoke-tested manually with the steps in `docs/DEMO_SCRIPT.md`.

## Environment variables

Copy `.env.example` to `backend/.env` and keep secrets backend-only. The important variables are:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `demo` (default) or `live`; live failures are surfaced, not silently mocked. |
| `DATABASE_PATH` | SQLite path for the synthetic demo dataset and local persistence. |
| `ZETARIS_BASE_URL` | Zetaris API origin for the opt-in adapter. |
| `ZETARIS_API_KEY` | Backend-only Zetaris bearer token. |
| `ZETARIS_ORG_ID` | Backend-only Zetaris organization header value. |
| `ZETARIS_DATASET_MODE` | `registered` for existing tables, or explicit `inline_synthetic` for demo rows computed by Zetaris without creating platform objects. |
| `MODEL_BASE_URL` | OpenAI-compatible endpoint; defaults to NVIDIA’s official endpoint. |
| `MODEL_API_KEY` | Backend-only model key. |
| `NEMOTRON_MODEL` | Configurable Nemotron model name. |
| `METERLESS_HMEM_ENABLED` | Opt in to the pinned local Meterless reference engine; false by default. Requires Node 24.22+. |
| `METERLESS_HMEM_NODE_BINARY` | Node executable path (defaults to `node`). No H-MEM endpoint or key needed. |

## Integration status and honesty boundary

The backend now embeds the genuine Meterless TypeScript reference engine through a local subprocess adapter. It passes the upstream conformance suite and a separate-process FastAPI restart/recall test. It stores findings, provenance, and an append-only trust ledger, and reinjects scored memories into investigation planning. The default flag remains false, retaining the prior fallback. No HTTP endpoint or key is used. See [verification and opt-in instructions](docs/HMEM_VERIFICATION.md).

The local Zetaris SqlEditor contract was verified: `POST /sql-editor/sqls/run` with `queryId`, `sql`, `source`, and `limit`, Bearer authentication, and organization/request headers. Returned `headers` and positional `data` rows are mapped into evidence records. The configured instance has no registered retail tables, so the verified runs explicitly used `inline_synthetic`: real Zetaris computation over supplied synthetic demo rows.

## Verified running application (2026-10-27)

- EvidenceTrail dashboard: `http://localhost:3001`. API: `http://127.0.0.1:8000/docs`. Zetaris retains port 3000 for its own UI.
- H-MEM is enabled in the local environment and confirmed active through `/api/config/status`. The safe code/example default remains false.
- Investigation `inv_ade1bbc6c0aa` completed with 5 Zetaris queries and 6 evidence items, then wrote memory `mem-1` and finding memories.
- After restarting FastAPI, investigation `inv_da06a4d6fd67` completed with 6 Zetaris queries, recalled `mem-1`, `mem-2`, and `mem-3`, and added a memory-informed validation query.
- Both used OpenRouter model `nvidia/nemotron-3.5-lightning:free`, returned by provider `Nvidia`, with validated JSON synthesis and response IDs recorded in their reports. No alternate model fallback was configured.
- Actual synthetic result: revenue fell from $82,344 to $80,406 (−2.35%). Trail Running Shoes fell $3,828, stockout days rose from 4 to 11, and supplier-delay evidence was present. These are contributors/associations, not proof of causality.

See [sponsor explanation and verification record](docs/SPONSOR_EXPLANATION.md). Reproduce through the running API with `backend/.venv/Scripts/python scripts/verify_live_investigation.py first`, then `second`. These commands make real configured service calls. Full reports are saved locally in ignored `data/live-verification-*.json` files.

## Known limitations

- Meterless runs locally when explicitly enabled; hosted Meterless connectivity is not claimed. Use one API worker per memory directory.
- Verified live execution used local Zetaris and OpenRouter Nemotron with synthetic SQL inputs. Production data federation, hosted deployment, and direct NVIDIA API connectivity were not verified.
- Demo analysis uses deterministic rule-based evidence extraction; it does not pretend to be an LLM result.
- Causality is not inferred from correlation alone. Reports explicitly distinguish association, contribution, and missing evidence.

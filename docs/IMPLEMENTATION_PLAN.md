# EvidenceTrail AI — Implementation Plan

## Goal

Deliver a hackathon-ready EvidenceTrail AI MVP for Track 2 (“The Agent That Can Explain Why”): a responsive investigation dashboard backed by a deterministic, evidence-first FastAPI workflow that can run locally without credentials and can switch to Zetaris/NVIDIA adapters when configured.

## Scope and assumptions

- The current workspace was empty, so this plan establishes a new monorepo under the workspace root.
- Demo mode is the default and uses synthetic retail data with documented ground-truth scenarios.
- The orchestration engine will be a small explicit state machine rather than LangGraph. This keeps progress observable, deterministic, and easy to test while preserving adapter boundaries for future sponsor integrations.
- H-MEM will be implemented as a local, persistent, Meterless-compatible reference adapter based on the official H-MEM specification. The official material describes the memory model and reference implementation, not a hosted HTTP SDK; therefore the app will not claim a live Meterless service until credentials/runtime details are supplied.
- Zetaris and NVIDIA adapters will be isolated behind interfaces. Live requests are opt-in and failures will be surfaced rather than silently changing to demo mode.

## Acceptance criteria

1. `backend` starts with FastAPI and exposes health, configuration, investigation, history, and report-download endpoints.
2. A demo-mode user can submit a natural-language retail question and receive a structured report grounded in actual sample-data queries.
3. The workflow exposes six user-visible stages and observable tool actions without hidden chain-of-thought.
4. Investigation summaries persist in H-MEM-compatible local memory; a related follow-up recalls prior context and records that it influenced planning.
5. The frontend provides Overview, New Investigation, Workspace/Report, History, and Settings views and connects to the backend.
6. Tests cover read-only SQL validation, evidence generation, contradiction/missing-evidence handling, H-MEM recall/reuse, API behavior, and the documented ground-truth scenarios.
7. README and docs explain local setup, environment variables, demo flow, limitations, and how to run live integration tests.

## Milestones

### Phase 1 — Foundation

- Add repository hygiene (`.gitignore`, `.env.example`, README skeleton).
- Add Python package with Pydantic settings, models, health/config endpoints, demo dataset generator, and adapters.
- Add Next.js App Router frontend with Tailwind styling and a small reusable UI system.

### Phase 2 — Working demo agent

- Implement deterministic investigation state machine:
  understand → plan → retrieve → evaluate → check → report.
- Implement restricted read-only SQL execution over the local SQLite demo dataset.
- Implement evidence records with provenance, supporting/contradicting evidence, confidence, and uncertainty.
- Implement H-MEM-compatible local memory store, retrieval, and “memory influenced plan” trace.
- Add investigation persistence and history endpoints.
- Connect the frontend to the end-to-end investigation journey.

### Phase 3 — Real integrations (modular, opt-in)

- Add verified Zetaris REST adapter for `/sql-editor/sqls/run` with Bearer, `X-Org-ID`, and `X-Request-ID` headers, bounded page limits/timeouts, and structured errors.
- Add NVIDIA Nemotron OpenAI-compatible adapter with retry/backoff, timeout, structured output validation, and usage metadata.
- Keep explicit live-mode failure states and add skipped-until-configured integration tests.

### Phase 4/5 — Quality and hackathon readiness

- Add broader API and frontend checks, downloadable Markdown/JSON reports, accessibility polish, demo script, submission checklist, and limitations.

## Verification commands

From `backend/`:

```bash
python -m pytest -q
```

From `frontend/`:

```bash
npm run lint
npm run build
```

Manual smoke flow:

1. Start the backend with `uvicorn app.main:app --reload --port 8000`.
2. Start the frontend with `npm run dev`.
3. Submit “Why did sales decrease in September 2025?” in Demo mode.
4. Confirm progress, queries, evidence, report download, and history reopen.
5. Submit a related stockout question and confirm the prior investigation memory trace is visible.

## Known blockers / honest limitations

- The Meterless public documentation currently available to this implementation defines H-MEM contracts/reference behavior but does not expose a stable hosted endpoint or Python SDK contract. The local adapter implements the documented memory behaviors, but it is not evidence of a live Meterless Engine connection.
- Zetaris live response shape is based on the official REST guide’s documented query body (`select`, `pageLimit`) plus the project-provided endpoint/header requirements; it remains unverified against a live tenant until credentials and an org are supplied.
- Official hackathon track-specific rules have not been provided, so sponsor-specific claims are intentionally kept modular and clearly labeled.

## Implementation status (2026-10-23)

- **Phase 1:** complete — monorepo foundation, configuration, seeded dataset, FastAPI health/config endpoints, and Next.js dashboard shell.
- **Phase 2:** complete — deterministic investigation workflow, read-only SQL, evidence/report models, history, downloads, local H-MEM recall/reuse, and connected dashboard flow.
- **Phase 3:** partial — Zetaris and NVIDIA adapters are implemented behind explicit configuration and tested for unconfigured failure; live calls remain unverified. H-MEM remains a local documented fallback until a verified Meterless runtime API is supplied.
- **Phase 4/5:** MVP checks and hackathon docs are present; authentication, tenant isolation, browser automation, and live integration tests remain follow-up work.

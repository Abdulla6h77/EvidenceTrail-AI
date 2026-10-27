# EvidenceTrail AI Architecture

## Runtime shape

```text
Next.js dashboard
        │ JSON over HTTP
        ▼
FastAPI API
  ├── InvestigationWorkflow (explicit state machine)
  │     ├── question parser
  │     ├── H-MEM retrieval before planning
  │     ├── safe query-plan builder
  │     ├── read-only SQL executor
  │     ├── evidence evaluator
  │     ├── contradiction/missing-control checker
  │     └── structured report + memory write
  ├── Local SQLite demo adapter
  ├── Zetaris REST adapter (opt-in)
  ├── NVIDIA Nemotron adapter (opt-in)
  ├── H-MEM-compatible local store
  └── JSON investigation history store
```

## Why a small state machine instead of LangGraph

The MVP needs six user-visible stages, deterministic demo output, and tests that can assert provenance. An explicit Python workflow is easier to inspect and keeps sponsor integrations modular. LangGraph can be introduced later if the investigation plan becomes dynamically branching or requires durable graph execution; the current adapter boundaries do not depend on that choice.

## Investigation lifecycle

1. **Understand question** — parse metric, entities, intent, target period, and comparison period.
2. **Create investigation plan** — retrieve relevant prior H-MEM summaries, then build only read-only query plans. If relevant memory mentions availability or suppliers, add an explicit memory-informed re-test query.
3. **Retrieve relevant data** — execute bounded SQL against the selected adapter and retain query provenance.
4. **Evaluate possible explanations** — create evidence records from actual rows, not generated claims.
5. **Check evidence** — add contradictory evidence when the outcome is concentrated rather than universal and always add missing causal controls.
6. **Generate final report** — produce findings, evidence IDs, confidence, uncertainty, recommendations, and query provenance; save a concise summary into H-MEM.

The frontend renders stage state and observable tool events. It never renders hidden chain-of-thought.

## Evidence model

Each evidence item has:

- a stable per-report `evidence_id`;
- direction: `supports`, `contradicts`, or `missing`;
- strength and confidence;
- the originating query ID when derived from data;
- fields/values and caveats;
- a clear distinction between association and causality.

Findings reference evidence IDs and use one of three causal labels:

- `not_established`;
- `possible_contributor`;
- `supported_contributor`.

`supported_contributor` means the observed data supports a contribution hypothesis; it is not a claim of deterministic causation.

## Persistence

Demo persistence is intentionally inspectable:

- `data/evidencetrail.db` — seeded synthetic retail tables;
- `data/evidencetrail.investigations.json` — report history;
- `data/evidencetrail.hmem.json` — H-MEM-compatible memory records.

These local files are ignored by Git. Production deployment should replace the JSON stores with a transactional database and add authentication/tenant scoping.

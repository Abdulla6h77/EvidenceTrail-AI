# Meterless H-MEM integration verification

Runtime activation update, 2026-10-27: H-MEM is now enabled in the actual local environment and running FastAPI application. Two investigations using real Zetaris and OpenRouter Nemotron completed, including a backend restart and successful recall. See [current service evidence](SPONSOR_EXPLANATION.md). The initial verification below describes the earlier test phase; the code and example default remain false.

Verified 2026-10-27. Reference commit `1742dec56a66e58eef9dda2d2b865823758ca8cd`.
Source: https://github.com/Meterless/Meterless/tree/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/hmem

The upstream root AGENTS.md, engine AGENTS.md, reference source, and conformance suite were inspected. No workspace-level AGENTS.md exists. The engine is an implementation spec plus executable reference, not a hosted service. The backend embeds the unmodified reference source with Apache-2.0 attribution in `backend/vendor/meterless-hmem/`. Python invokes it over local stdin/stdout. There are no new runtime npm dependencies, URLs, or keys.

## Enable after verification

The default and `.env.example` remain `METERLESS_HMEM_ENABLED=false`. Existing environment files were not edited. To use the verified engine, set `METERLESS_HMEM_ENABLED=true` in the backend environment and restart with one Uvicorn worker. Node 24.22.1 was tested, using `--experimental-transform-types`; earlier Node releases are not supported by this integration. Set `METERLESS_HMEM_NODE_BINARY` to an absolute executable path if necessary.

The flag selects the local reference engine in both demo and live application environments. It does not enable live data or model calls. A missing Node runtime or malformed engine state raises an explicit error; it never silently switches adapters.

## Storage and behavior

- Existing retail SQLite and investigation JSON storage stay in place.
- Existing `*.hmem.json` fallback memories remain intact. They are not silently migrated into trusted reference records. Turning the flag off restores use of the fallback.
- New engine data is adjacent to the SQLite file in `<database-stem>.meterless-hmem/state.json` and `ledger.jsonl`.
- Each completed investigation writes a concise summary and individual findings to working memory. Findings retain confidence and evidence references; summary provenance references query IDs. These are synthetic demo observations requiring revalidation, not approved universal knowledge.
- Engine enrichment, graph links, canonical ranking, threshold 0.35, feedback deltas, and trust ledger come from upstream source. Read usage is explicitly flushed before the subprocess exits.
- Subsequent investigations receive domain-grouped context, IDs, relevance scores, and provenance in the report trace. Availability-related memories trigger a fresh SQL validation query. Memories never become new evidence without querying current data.
- The report is saved again after memory writes so its stored memory ID survives restart.

## Verification results

1. Upstream conformance suite against the vendored engine: **13/13 passed**, exit 0. Covers source rejection, feedback arithmetic/clamping, ranking ordering, sleep guardrails, conflict resolution, audit snapshots, and dream approval boundary.
2. Backend suite: **9 passed, 1 skipped**, exit 0. Includes persistence, provenance, feedback ledger, corrupt-state rejection, and separate-process FastAPI restart. The skipped test is the pre-existing hosted Meterless placeholder; no hosted connection is claimed.
3. Restart demonstration, two independent TestClient application lifecycles in separate Python processes:

```json
{"phase":"write","pid":2160,"investigation_id":"inv_75324359d631","memory_id":"mem-1","recalled_ids":[],"memory_influenced_plan":false}
{"phase":"recall","pid":17136,"investigation_id":"inv_1f54c54baf69","memory_id":"mem-5","recalled_ids":["mem-1","mem-2","mem-3"],"memory_influenced_plan":true,"prior_report_preserved":true}
```

Run from the repository root with a fresh disposable database path:

```powershell
backend/.venv/Scripts/python scripts/hmem_restart_demo.py write data/hmem-demo-new.db
backend/.venv/Scripts/python scripts/hmem_restart_demo.py recall data/hmem-demo-new.db
$env:HMEM_IMPL = (Resolve-Path backend/vendor/meterless-hmem/src/index.ts).Path
node --experimental-transform-types backend/vendor/meterless-hmem/conformance/runner.ts
cd backend
.venv/Scripts/python -m pytest -q
```

The demo explicitly enables the adapter only in its Settings instance. It does not modify environment files. API tests required unsandboxed execution because the sandbox blocked Python asyncio's internal loopback socketpair. Verification used Python 3.13.15, FastAPI 0.115.12, Starlette 0.46.2, and Node 24.22.1. The upstream Vitest smoke suite was not run; the standalone upstream conformance runner was run directly with Node.

## Unsupported or limited in the application

- Dreaming, sleep, conflict management, and general interaction/document mining exist in the vendored engine and their applicable conformance checks pass, but are not exposed or scheduled by FastAPI. No autonomous synthesis or destructive maintenance is enabled.
- The application captures completed findings directly; it does not use a model extraction pipeline. Embeddings are upstream deterministic hashes, not a semantic embedding service. Related paraphrases can miss the threshold. Restart proof changes the question from “Why did sales decrease in September 2025?” to “Why did sales decrease in September 2025 with stockouts?”. Zero recall is preserved.
- No feedback UI or HTTP memory-management endpoints. The Python adapter supports feedback and inspection for local verification.
- JSON reference persistence is for a single API worker. The Python lock serializes calls in that process, but there is no cross-process locking, transaction spanning state and ledger, or crash-atomic durability guarantee. Back up both files together. Multiworker deployment is unsupported.
- No authentication or tenant isolation added. Goal-run isolation, volatile short-term tier semantics, long-term decay/migration behavior, and durable dream/sleep session recovery are not certified by this integration or the 13-check suite. No claim of complete production H-MEM compliance.

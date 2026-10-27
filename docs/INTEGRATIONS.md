# Integration Notes

## Meterless H-MEM

Sources reviewed: Meterless Engines page (`https://meterless.ai/engines.html`) and the linked open-source H-MEM implementation/specification (`https://github.com/Meterless/Meterless/tree/main/engines/hmem`).

The Meterless public material reviewed for this project describes an H-MEM architecture and deterministic reference implementation. The documented contracts used here include:

- canonical records with `id`, `content`, `layer`, timestamps, confidence, source, provenance, tags, entities, and relationship fields;
- tiered short-term/working/long-term memory;
- hybrid retrieval with lexical/semantic-style scoring, confidence weighting, and top-N selection;
- explicit retrieval trace metadata;
- audit-friendly mutation behavior;
- model-free direct-capture fallback.

The backend now embeds the pinned, unmodified Meterless reference engine through `ReferenceHMEMStore` in `backend/app/integrations/hmem.py`. It runs locally under Node and persists `state.json` plus the append-only `ledger.jsonl`. Findings carry provenance and evidence references. Retrieved memories include relevance scores and grouped context and trigger fresh validation queries. The existing `local_hmem_fallback` remains the default while the reference-engine flag is false.

**Verification:** the reference engine passed all 13 upstream conformance checks. A separate-process FastAPI write/restart/recall test passes. `METERLESS_HMEM_ENABLED=true` explicitly selects this verified local runtime; the default remains false. No HTTP endpoint or API key is needed or invented. See [verification, setup, and limits](HMEM_VERIFICATION.md).

The reference-engine proof is `backend/tests/test_meterless_reference.py::test_fastapi_restart_in_separate_processes` and `scripts/hmem_restart_demo.py`:

1. Run Investigation A.
2. Assert its summary was stored.
3. Exit the process, restart the FastAPI application in another Python process, and run related Investigation B.
4. Assert a prior memory ID was retrieved.
5. Assert `memory_influenced_plan` is true and a memory-informed query plan exists.

## Zetaris

The official Zetaris REST guide reviewed for this MVP documents:

- the Open SQL query body fields `select` and `pageLimit`;
- `pageLimit` values from 1 to 100;
- query pagination and query closing concepts;
- bearer-token configuration in the API collection.

The hackathon contract additionally requires:

- `POST /sql-editor/sqls/run`;
- `Authorization: Bearer ...`;
- `X-Org-ID`;
- `X-Request-ID`.

The installed SqlEditor endpoint is a different contract from the older Open SQL guide. On 2026-10-27, the actual server required `queryId`, `sql`, `source: SqlEditor`, and `limit`. Its response has `headers`, positional `data`, `total`, and `timeUsed`. The adapter now uses this verified contract, maps columns, rejects malformed/truncated results, validates read-only SQL, and records request IDs and elapsed time. Reference: [official starter REST implementation](https://github.com/zetaris/getting-started/blob/main/scripts/zetaris_sql.py).

Two complete investigations were verified against the user's local Zetaris service. The stopped existing driver container was started. No retail tables were registered, so the local environment explicitly selects `ZETARIS_DATASET_MODE=inline_synthetic`. This transmits the public deterministic demo rows as SQL VALUES CTEs and performs computation in Zetaris. It creates no platform tables and does not claim production business data or source federation. Registered-table mode remains the default for other installations.

## NVIDIA Nemotron

`backend/app/integrations/nemotron.py` targets the OpenAI-compatible chat-completions shape at:

```text
MODEL_BASE_URL=https://integrate.api.nvidia.com/v1
```

The configured and verified endpoint is `https://openrouter.ai/api/v1`, with model `nvidia/nemotron-3.5-lightning:free` and provider `Nvidia`. The direct NVIDIA endpoint above remains the code default and was not verified. [OpenRouter's documented chat format](https://openrouter.ai/docs/api/reference/overview) is used without a model fallback list.

The model name and API key stay backend-only. Live investigations derive evidence deterministically from actual Zetaris rows, then pass that evidence and the recalled memory context to Nemotron for JSON summary, evidence citations, and uncertainty. Pydantic validates the result and the workflow rejects references to nonexistent evidence IDs. Reports retain requested/returned model, endpoint host, provider, response ID, and token usage. Demo mode remains deterministic and makes no model call.

The OpenRouter request disables reasoning and allows up to 8192 output tokens to leave room for valid structured output. Earlier attempts with a 2048-token allowance failed root-object validation and were recorded as failed investigations, without memory writes. The precise contents of those rejected responses were not retained; no successful result is claimed for them. Live model failures do not produce a demo fallback. See [observed results](SPONSOR_EXPLANATION.md).

## Connection states

The Settings screen distinguishes:

- **ready** — local demo capability or configured adapter;
- **not_configured** — credentials are absent;
- **error** — a live call failed (reported by the adapter/API);
- **demo** vs **live** mode.

No live integration is silently replaced with demo data.

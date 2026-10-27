# EvidenceTrail AI sponsor explanation

Verified 2026-10-27, 21:50–21:51 Asia/Karachi. This record describes observed local service execution, not a hosted deployment or organizer certification.

EvidenceTrail investigates a business change by querying data, deriving an evidence ledger, checking missing controls and contradictions, generating a cited explanation, and retaining findings for later revalidation.

## What each integration actually did

**Zetaris:** The real local SqlEditor service executed all investigation SQL. We verified its request contract against the running server and the [official starter implementation](https://github.com/zetaris/getting-started/blob/main/scripts/zetaris_sql.py). The existing driver container was stopped; starting it restored query execution. The API alone had been healthy while SQL timed out.

The instance had no registered `monthly_sales` table. The application therefore uses explicitly configured `inline_synthetic` mode for this demonstration: deterministic synthetic rows are supplied as read-only VALUES CTEs and computed in Zetaris. This is genuine Zetaris execution, but not production retail data or a demonstrated multi-source federation. No new platform tables or cloud resources were created. Original SQLite data and investigation history remain intact.

**NVIDIA Nemotron through OpenRouter:** `nvidia/nemotron-3.5-lightning:free` synthesized the actual returned evidence into a summary with cited evidence IDs and uncertainty. OpenRouter reported provider `Nvidia` and the same requested/returned model for both completed runs. Reports store response IDs and usage; the workflow validates JSON and rejects evidence IDs outside the current investigation. Evidence and finding rules remain deterministic. The direct NVIDIA endpoint was not tested. No alternate model fallback was configured.

**Meterless H-MEM:** The pinned Apache-2.0 reference engine runs locally through the Python adapter. It wrote summaries and individual findings, retained provenance and confidence, appended trust-ledger entries, reloaded after FastAPI restart, and recalled relevant memories into the second plan and model input. Recalled availability hypotheses triggered a new SQL check. Memories were not treated as newly observed evidence. No H-MEM HTTP endpoint, API key, or hosted connection was invented.

## Observed runs

| Result | First investigation | Second, after FastAPI restart |
|---|---|---|
| Investigation ID | `inv_ade1bbc6c0aa` | `inv_da06a4d6fd67` |
| Question | Why did sales decrease in September 2025? | Why did sales decrease in September 2025 with stockouts? |
| Status | completed, no errors | completed, no errors |
| Zetaris queries | 5 | 6 |
| Returned row counts | 2, 12, 12, 12, 2 | 2, 12, 12, 12, 2, 2 |
| Evidence items | 6 | 6 |
| OpenRouter response ID | `gen-1793119844-DcXdPfc94gH8SD5cPPX0` | `gen-1793119868-gzeAKNLOtZ1SpiTKKp1P` |
| Prompt / completion tokens | 1231 / 282 | 1461 / 273 |
| Reported cost | 0 | 0 |
| Written summary memory | `mem-1` | `mem-5` |
| Recalled memories | none | `mem-1`, `mem-2`, `mem-3` |
| Memory changed plan | false | true |

Second-run relevance scores were 0.6194, 0.4322, and 0.3581, above the engine's 0.35 threshold. The extra query re-tested nonzero stockout days. The verification script also confirmed the first report could be reopened unchanged after restart. Local full reports are in ignored `data/live-verification-first.json` and `data/live-verification-second.json`.

Revenue changed from **$82,344 in August to $80,406 in September 2025**, a **2.35% decline**. Trail Running Shoes revenue fell $3,828, stockout days rose from 4 to 11, and the dataset contained a 13-day supplier delay affecting two purchase orders. Other products held steady or improved. The model explicitly acknowledged that stockouts do not establish lost demand or causality and that observational data cannot isolate causal impact.

## Failures and remaining limits

Initial connectivity probes identified a request-contract mismatch and stopped driver. Three initial full investigations then failed model schema validation and wrote no H-MEM records. They remain marked failed in local history. A direct structured-output diagnostic succeeded. The completed runs followed a clearer object prompt, a larger bounded output allowance, and disabling reasoning for OpenRouter synthesis. Exact rejected response contents were not retained, so their detailed root cause is not asserted.

This is a single-worker hackathon integration with JSON memory persistence, deterministic embeddings, and synthetic inputs. It has no production authentication or tenant isolation. Dreaming, sleep maintenance, and conflict-management workflows are not scheduled or exposed by the application. A green conformance suite certifies its tested reference contracts, not full production durability or complete H-MEM semantics.

## Verification and credential handling

- Backend regression and mocked live-boundary tests: 13 passed, 1 hosted-service placeholder skipped. Mocked tests are separate from the two real runs above.
- Upstream Meterless conformance: 13/13 checks passed.
- Dashboard `http://localhost:3001`, API `http://127.0.0.1:8000/docs`, health endpoint, active H-MEM status, and dashboard CORS were checked. No browser-based UI interaction is claimed.
- Keys stay in the ignored local environment and are read only by the backend. No credentials are passed to the frontend or stored in verification reports.
- An exact-value scan of source, documentation, configuration templates, reports, and logs found no configured API keys. Local environment files were excluded intentionally. The workspace has no `.git` repository, and no Git commit or push was performed.

To reproduce with configured credentials, run `scripts/verify_live_investigation.py first`, restart the single FastAPI worker if testing cross-session durability, then run `scripts/verify_live_investigation.py second` using the backend Python environment. These are real service calls. Settings readiness alone is not a connectivity test; the report query and model provenance provide the execution evidence.

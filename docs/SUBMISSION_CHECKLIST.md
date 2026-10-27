# Hackathon Submission Checklist

## Product proof

- [x] User can submit an investigation in a dashboard.
- [x] Demo mode works without external credentials.
- [x] Actual data queries and outputs are visible.
- [x] Supporting, contradicting, and missing evidence are distinct.
- [x] Confidence and uncertainty are explicit.
- [x] Report recommendations point back to evidence IDs.
- [x] Investigation history and reopen flow work.
- [x] JSON and Markdown report downloads work.

## Agent / memory proof

- [x] Explicit six-stage investigation workflow.
- [x] No hidden chain-of-thought rendered.
- [x] H-MEM-compatible local memory is functional and persistent.
- [x] Related follow-up retrieves prior memory.
- [x] Retrieved memory changes the follow-up plan.
- [x] Genuine local Meterless reference engine used by two real-service investigations, with recall after FastAPI restart. No hosted Meterless service or key claimed.

## Sponsor integrations

- [x] Zetaris adapter boundary implemented with requested endpoint and headers.
- [x] Local Zetaris SqlEditor request/response and complete investigation queries verified over explicit synthetic SQL inputs.
- [x] NVIDIA OpenAI-compatible adapter implemented with configurable model, timeout, retries, and structured validation.
- [x] Nemotron verified through OpenRouter's Nvidia provider; direct NVIDIA API connectivity remains unverified.

## Reliability and honesty

- [x] No credentials in frontend.
- [x] `.env.example` and `.gitignore` included.
- [x] Read-only SQL validation and row bounds included.
- [x] Live mode does not silently fall back to demo mode.
- [x] Synthetic data and known scenarios documented.
- [x] Causal claims are explicitly limited.
- [ ] Add authentication/tenant isolation before production use.

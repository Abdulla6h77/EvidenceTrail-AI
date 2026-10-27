# Meterless H-MEM source

Source: https://github.com/Meterless/Meterless/tree/1742dec56a66e58eef9dda2d2b865823758ca8cd/engines/hmem

Retrieved 2026-10-27. Apache-2.0, see LICENSE.
`src/` and `conformance/` are unmodified upstream files. SPEC.md is upstream AGENTS.md.
`bridge.ts` is the EvidenceTrail local stdin/stdout transport, not an HTTP API.
Node 24.22.1 with --experimental-transform-types was verified. No npm packages required.

Run the upstream suite from the workspace root (PowerShell):

```powershell
$env:HMEM_IMPL = (Resolve-Path backend/vendor/meterless-hmem/src/index.ts).Path
node --experimental-transform-types backend/vendor/meterless-hmem/conformance/runner.ts
```

// EvidenceTrail transport only. Engine behavior lives in the pinned upstream src/.
import fs from "node:fs";
import { HMEM } from "./src/index.ts";

const request = JSON.parse(fs.readFileSync(0, "utf8"));
fs.mkdirSync(request.persistDir, { recursive: true });
const engine = new HMEM({ persistDir: request.persistDir, actor: "evidencetrail" });
let result;
switch (request.action) {
  case "add": result = engine.add(request.input); break;
  case "query":
    result = engine.query(request.query, { topN: request.topN });
    // Upstream touch() mutates usage in memory; flush it before process exit.
    engine.store.persist();
    break;
  case "feedback": engine.feedback(request.id, request.kind); result = true; break;
  case "inspect": result = { records: engine.store.all(), ledger: engine.ledger.all() }; break;
  default: throw new Error("Unknown H-MEM bridge action");
}
process.stdout.write(JSON.stringify(result));

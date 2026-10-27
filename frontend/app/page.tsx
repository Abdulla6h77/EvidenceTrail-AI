"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type View = "overview" | "new" | "history" | "settings" | "workspace";
type Status = "queued" | "running" | "completed" | "failed" | "pending" | "not_configured" | "ready";

type Connectivity = {
  name: string;
  status: Status;
  mode: "demo" | "live";
  detail: string;
};

type Stage = {
  name: string;
  label: string;
  status: Status;
  detail?: string | null;
};

type Evidence = {
  evidence_id: string;
  statement: string;
  direction: "supports" | "contradicts" | "missing";
  strength: string;
  confidence: number;
  source_query_id?: string | null;
  caveat?: string | null;
};

type Finding = {
  finding_id: string;
  title: string;
  explanation: string;
  evidence_ids: string[];
  confidence: number;
  uncertainty: string;
  causal_claim: string;
};

type Recommendation = {
  action: string;
  rationale: string;
  priority: string;
  evidence_ids: string[];
};

type Report = {
  question: string;
  executive_summary: string;
  findings: Finding[];
  evidence: Evidence[];
  recommendations: Recommendation[];
  uncertainty: string[];
  query_provenance: { query_id: string; sql: string; row_count: number; duration_ms: number }[];
  memory_trace: { retrieved: boolean; influenced_plan: boolean; memory_ids: string[]; stored_memory_id?: string | null; note?: string | null };
};

type Investigation = {
  id: string;
  request: { question: string; dataset: string; mode: "demo" | "live" };
  status: Status;
  created_at: string;
  updated_at: string;
  stages: Stage[];
  plan?: { plans: { purpose: string; sql: string; hypothesis: string }[]; memory_influenced_plan: boolean; memory_note?: string | null } | null;
  queries: { provenance: { query_id: string; sql: string; row_count: number; duration_ms: number }; rows: Record<string, unknown>[]; error?: string | null }[];
  tool_events: string[];
  errors: string[];
  report?: Report | null;
};

type Overview = {
  total_investigations: number;
  recent_investigations: Investigation[];
  connectivity: Connectivity[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

const suggestions = [
  "Why did sales decrease in September 2025?",
  "Are stockouts contributing to lost sales?",
  "Did pricing changes affect demand for products?",
  "Which suppliers are associated with inventory disruptions?",
];

const navigation: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "⌂" },
  { id: "new", label: "New investigation", icon: "+" },
  { id: "history", label: "Investigation history", icon: "◷" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

function statusClass(status: Status) {
  return `status-badge status-${status}`;
}

function formatDate(value?: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export default function HomePage() {
  const [view, setView] = useState<View>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [history, setHistory] = useState<Investigation[]>([]);
  const [selected, setSelected] = useState<Investigation | null>(null);
  const [question, setQuestion] = useState(suggestions[0]);
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingPage, setLoadingPage] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async () => {
    try {
      setError(null);
      const [nextOverview, nextHistory] = await Promise.all([
        apiFetch<Overview>("/overview"),
        apiFetch<{ investigations: Investigation[] }>("/investigations"),
      ]);
      setOverview(nextOverview);
      setHistory(nextHistory.investigations);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the backend");
    } finally {
      setLoadingPage(false);
    }
  };

  useEffect(() => {
    // This effect intentionally starts an async external-data synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDashboard();
  }, []);

  const openInvestigation = async (id: string) => {
    try {
      setError(null);
      const investigation = await apiFetch<Investigation>(`/investigations/${id}`);
      setSelected(investigation);
      setView("workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open investigation");
    }
  };

  const submitInvestigation = async (event: FormEvent) => {
    event.preventDefault();
    if (question.trim().length < 8) {
      setError("Please enter a question with enough context to investigate.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const investigation = await apiFetch<Investigation>("/investigations", {
        method: "POST",
        body: JSON.stringify({ question, dataset: "synthetic_retail", mode }),
      });
      setSelected(investigation);
      setView("workspace");
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start investigation");
    } finally {
      setLoading(false);
    }
  };

  const filteredHistory = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return history;
    return history.filter((item) => item.request.question.toLowerCase().includes(needle));
  }, [history, search]);

  const currentTitle = view === "workspace" ? "Investigation workspace" : navigation.find((item) => item.id === view)?.label || "Overview";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">E</div>
          <div>
            <div className="brand-name">EvidenceTrail</div>
            <div className="brand-subtitle">Explain why, with evidence</div>
          </div>
        </div>
        <div className="nav-label">Workspace</div>
        <nav className="nav" aria-label="Primary navigation">
          {navigation.map((item) => (
            <button key={item.id} className={`nav-button ${view === item.id ? "active" : ""}`} onClick={() => setView(item.id)}>
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
          {selected && (
            <button className={`nav-button ${view === "workspace" ? "active" : ""}`} onClick={() => setView("workspace")}>
              <span className="nav-icon" aria-hidden="true">◈</span>
              <span>Current report</span>
            </button>
          )}
        </nav>
        <div className="side-footer">
          <div className="mode-pill"><span>Environment</span><span>DEMO</span></div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="crumb">EvidenceTrail AI / {currentTitle}</div>
            <div className="topbar-title">Investigation intelligence</div>
          </div>
          <div className="topbar-actions">
            <div className="connection-chip"><span className="dot" /> Local data source ready</div>
            <div className="avatar">ET</div>
          </div>
        </header>

        <div className="content">
          {error && <div className="error-box" role="alert">{error}</div>}
          {loadingPage ? (
            <div className="panel empty">Loading EvidenceTrail workspace…</div>
          ) : (
            <>
              {view === "overview" && (
                <OverviewView overview={overview} onNew={() => setView("new")} onOpen={openInvestigation} />
              )}
              {view === "new" && (
                <NewInvestigationView
                  question={question}
                  setQuestion={setQuestion}
                  mode={mode}
                  setMode={setMode}
                  loading={loading}
                  onSubmit={submitInvestigation}
                  onCancel={() => setView("overview")}
                />
              )}
              {view === "history" && (
                <HistoryView search={search} setSearch={setSearch} history={filteredHistory} onOpen={openInvestigation} />
              )}
              {view === "settings" && <SettingsView connectivity={overview?.connectivity || []} />}
              {view === "workspace" && selected && (
                <WorkspaceView investigation={selected} onBack={() => setView("history")} />
              )}
              {view === "workspace" && !selected && (
                <div className="panel empty">Submit an investigation to open the workspace.</div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function OverviewView({ overview, onNew, onOpen }: { overview: Overview | null; onNew: () => void; onOpen: (id: string) => void }) {
  const recent = overview?.recent_investigations || [];
  const readyCount = (overview?.connectivity || []).filter((item) => item.status === "ready").length;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">Evidence-first analysis</div>
          <h1>See what changed.<br />Understand why.</h1>
          <p className="lede">EvidenceTrail turns a business question into an auditable investigation: actual queries, supporting and contradicting signals, honest uncertainty, and next actions.</p>
        </div>
        <button className="primary-button" onClick={onNew}>＋ New investigation</button>
      </div>

      <div className="stat-grid">
        <div className="stat-card"><div className="stat-top"><span>Total investigations</span><span>◈</span></div><div className="stat-value">{overview?.total_investigations || 0}</div><div className="stat-change">Local history</div></div>
        <div className="stat-card"><div className="stat-top"><span>Completed reports</span><span>✓</span></div><div className="stat-value">{recent.filter((item) => item.status === "completed").length}</div><div className="stat-change">Evidence-backed</div></div>
        <div className="stat-card"><div className="stat-top"><span>Data sources ready</span><span>⌁</span></div><div className="stat-value">{readyCount}<span style={{ fontSize: 16, color: "#8d98a9" }}> / {(overview?.connectivity || []).length}</span></div><div className="stat-change">Demo mode active</div></div>
        <div className="stat-card"><div className="stat-top"><span>Memory recall</span><span>↺</span></div><div className="stat-value">H-MEM</div><div className="stat-change">Local fallback ready</div></div>
      </div>

      <div className="grid-two">
        <section className="panel">
          <div className="panel-header"><div><div className="panel-title">Recent investigations</div><div className="panel-subtitle">Open a report to inspect its evidence trail.</div></div><button className="secondary-button" onClick={() => onNew()}>Start one</button></div>
          <div className="history-list">
            {recent.length === 0 ? <div className="empty">No investigations yet. Start with a question about the synthetic retail dataset.</div> : recent.map((item) => <InvestigationRow key={item.id} item={item} onOpen={onOpen} />)}
          </div>
        </section>
        <section className="panel">
          <div className="panel-header"><div><div className="panel-title">Connectivity</div><div className="panel-subtitle">Live integrations stay explicit and credential-gated.</div></div><span className="tag">STATUS</span></div>
          <div className="status-list">{(overview?.connectivity || []).map((item) => <StatusRow key={item.name} item={item} />)}</div>
        </section>
      </div>
    </>
  );
}

function NewInvestigationView({ question, setQuestion, mode, setMode, loading, onSubmit, onCancel }: { question: string; setQuestion: (value: string) => void; mode: "demo" | "live"; setMode: (value: "demo" | "live") => void; loading: boolean; onSubmit: (event: FormEvent) => void; onCancel: () => void }) {
  return (
    <>
      <div className="page-heading"><div><div className="eyebrow">Start with a measurable outcome</div><h1>New investigation</h1><p className="lede">Ask a natural-language question. EvidenceTrail will parse the period, create safe read-only queries, test multiple explanations, and show what remains uncertain.</p></div></div>
      <div className="form-layout">
        <form className="panel" onSubmit={onSubmit}>
          <div className="form-field"><label className="form-label" htmlFor="question">What changed, and why do you want to understand it?</label><textarea id="question" className="textarea" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Example: Why did sales decrease in September 2025?" /><span className="form-hint">Tip: include a metric and time period for a sharper comparison.</span></div>
          <div className="form-field"><label className="form-label" htmlFor="dataset">Dataset</label><select id="dataset" className="select" defaultValue="synthetic_retail"><option value="synthetic_retail">Synthetic retail — sales, inventory, suppliers</option></select></div>
          <div className="form-field"><label className="form-label" htmlFor="mode">Execution mode</label><select id="mode" className="select" value={mode} onChange={(event) => setMode(event.target.value as "demo" | "live")}><option value="demo">Demo — deterministic local data</option><option value="live">Live — credential-gated integrations</option></select><span className="form-hint">Live mode never silently falls back to demo data.</span></div>
          <div className="form-actions"><button type="button" className="secondary-button" onClick={onCancel}>Cancel</button><button type="submit" className="primary-button" disabled={loading}>{loading ? "Investigating…" : "Start investigation →"}</button></div>
        </form>
        <aside className="panel"><div className="panel-header"><div><div className="panel-title">Try a question</div><div className="panel-subtitle">Each example maps to real demo fields.</div></div></div><div className="suggestion-list">{suggestions.map((item) => <button className="suggestion" key={item} onClick={() => setQuestion(item)}>{item}</button>)}</div><div style={{ marginTop: 22 }} className="memory-banner"><strong>Memory-aware by design.</strong><br />A completed investigation is saved as a concise evidence-backed summary. Related follow-ups can recall it and show exactly when it influenced the plan.</div></aside>
      </div>
    </>
  );
}

function WorkspaceView({ investigation, onBack }: { investigation: Investigation; onBack: () => void }) {
  const report = investigation.report;
  return (
    <>
      <div className="page-heading"><div><div className="eyebrow">{investigation.id} · {investigation.request.mode.toUpperCase()} MODE</div><h1>Investigation workspace</h1><p className="lede">{investigation.request.question}</p></div><div style={{ display: "flex", gap: 9 }}><button className="secondary-button" onClick={onBack}>← History</button>{report && <><a className="secondary-button" href={`${API_BASE}/investigations/${investigation.id}/report?format=markdown`}>Download Markdown</a><a className="secondary-button" href={`${API_BASE}/investigations/${investigation.id}/report?format=json`}>JSON</a></>}</div></div>
      {investigation.errors.length > 0 && <div className="error-box">{investigation.errors.join(" ")}</div>}
      <div className="report-layout">
        <div className="panel">
          <div className="panel-header"><div><div className="panel-title">Observable progress</div><div className="panel-subtitle">Concise steps and tool actions — no hidden reasoning traces.</div></div><span className={statusClass(investigation.status)}>{investigation.status}</span></div>
          <div className="stage-list">{investigation.stages.map((stage, index) => <div className={`stage ${stage.status}`} key={stage.name}><div className="stage-icon">{stage.status === "completed" ? "✓" : stage.status === "running" ? "…" : index + 1}</div><div><div className="stage-name">{stage.label}</div><div className="stage-detail">{stage.detail || "Waiting for this stage"}</div></div><div className="stage-status">{stage.status}</div></div>)}</div>
          <div style={{ marginTop: 24 }}><div className="panel-title" style={{ marginBottom: 11 }}>Executed tool actions</div><div className="evidence-list">{investigation.tool_events.map((event, index) => <div className="evidence" key={`${event}-${index}`}><div className="evidence-id">TOOL EVENT {String(index + 1).padStart(2, "0")}</div>{event}</div>)}</div></div>
        </div>
        <div className="panel"><div className="panel-header"><div><div className="panel-title">Memory trace</div><div className="panel-subtitle">Recall is shown only when it happened.</div></div><span className="tag">H-MEM</span></div>{report?.memory_trace.retrieved ? <div className="memory-banner"><strong>Prior memory retrieved and used.</strong><br />{report.memory_trace.note || "Relevant prior investigation context influenced the plan."}<br /><span style={{ opacity: .8 }}>Memory IDs: {report.memory_trace.memory_ids.join(", ")}</span></div> : <div className="empty" style={{ paddingTop: 10 }}>No prior memory was retrieved for this investigation. A summary was stored after the report completed.</div>}{report?.memory_trace.stored_memory_id && <div className="form-hint">Stored summary: {report.memory_trace.stored_memory_id}</div>}</div>
      </div>
      {report && <ReportView report={report} queries={investigation.queries} />}
    </>
  );
}

function ReportView({ report, queries }: { report: Report; queries: Investigation["queries"] }) {
  return (
    <div style={{ marginTop: 20 }} className="grid-two">
      <section className="panel"><div className="panel-header"><div><div className="panel-title">Investigation report</div><div className="panel-subtitle">Grounded findings with supporting and contradicting evidence.</div></div><span className="tag">REPORT</span></div><div className="summary-card">{report.executive_summary}</div><div style={{ marginTop: 20 }}>{report.findings.map((finding) => <div className="finding" key={finding.finding_id}><div className="finding-title">{finding.title}</div><div className="finding-text">{finding.explanation}</div><div className="finding-foot"><span className="confidence">{formatPercent(finding.confidence)} confidence</span><span className="tag">{finding.causal_claim.replaceAll("_", " ")}</span><span>{finding.uncertainty}</span></div></div>)}</div><div style={{ marginTop: 21 }}><div className="panel-title" style={{ marginBottom: 11 }}>Recommended actions</div>{report.recommendations.map((item, index) => <div className="recommendation" key={`${item.action}-${index}`}><div className="priority">{item.priority.toUpperCase()}</div><div className="recommendation-text"><strong>{item.action}</strong><br /><span className="muted">{item.rationale}</span></div></div>)}</div></section>
      <aside className="panel"><div className="panel-header"><div><div className="panel-title">Evidence ledger</div><div className="panel-subtitle">Every item is labeled by direction and provenance.</div></div></div><div className="evidence-list">{report.evidence.map((item) => <div className={`evidence ${item.direction}`} key={item.evidence_id}><div className="evidence-id">{item.evidence_id} · {item.direction.toUpperCase()} · {formatPercent(item.confidence)}</div>{item.statement}{item.caveat && <div style={{ marginTop: 5, color: "#8a6b31" }}>Caveat: {item.caveat}</div>}</div>)}</div><div style={{ marginTop: 22 }}><div className="panel-title" style={{ marginBottom: 10 }}>Uncertainty</div><div className="evidence-list">{report.uncertainty.map((item) => <div className="evidence missing" key={item}>{item}</div>)}</div></div></aside>
      <section className="panel" style={{ gridColumn: "1 / -1" }}><div className="panel-header"><div><div className="panel-title">Executed SQL and provenance</div><div className="panel-subtitle">Read-only queries, bounded outputs, and errors from the selected data source.</div></div><span className="tag">{queries.length} QUERIES</span></div><div className="evidence-list">{queries.map((query) => <div className="query" key={query.provenance.query_id}><div className="query-summary"><span><strong>{query.provenance.query_id}</strong> · {query.provenance.row_count} rows · {query.provenance.duration_ms} ms</span><span className="query-id">local_sqlite_demo</span></div><pre>{query.provenance.sql}</pre>{query.error && <div className="error-box" style={{ margin: 0, borderRadius: 0 }}>{query.error}</div>}<details style={{ borderTop: "1px solid #e7ebf2" }}><summary style={{ padding: "10px 12px", color: "#536071", fontSize: 11, cursor: "pointer" }}>Show tool output ({query.rows.length} returned row(s))</summary><pre style={{ background: "#f8fafc", color: "#536071" }}>{JSON.stringify(query.rows.slice(0, 8), null, 2)}</pre></details></div>)}</div></section>
    </div>
  );
}

function HistoryView({ search, setSearch, history, onOpen }: { search: string; setSearch: (value: string) => void; history: Investigation[]; onOpen: (id: string) => void }) {
  return <><div className="page-heading"><div><div className="eyebrow">Auditable workspace</div><h1>Investigation history</h1><p className="lede">Reopen reports, inspect the evidence ledger, and see whether prior memory was reused.</p></div><button className="primary-button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>History is persistent</button></div><section className="panel"><div className="toolbar"><div><div className="panel-title">All investigations</div><div className="panel-subtitle">{history.length} result(s)</div></div><input className="input toolbar-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search questions…" /></div><div className="history-list">{history.length === 0 ? <div className="empty">No matching investigations.</div> : history.map((item) => <InvestigationRow key={item.id} item={item} onOpen={onOpen} />)}</div></section></>;
}

function SettingsView({ connectivity }: { connectivity: Connectivity[] }) {
  return <><div className="page-heading"><div><div className="eyebrow">Configuration boundary</div><h1>Settings</h1><p className="lede">Keep credentials on the backend. Live integrations are modular, explicit, and never silently replaced by demo data.</p></div></div><div className="grid-two"><section className="panel"><div className="panel-header"><div><div className="panel-title">Connection status</div><div className="panel-subtitle">Environment values are read by the FastAPI backend.</div></div></div><div className="status-list">{connectivity.map((item) => <StatusRow item={item} key={item.name} />)}</div></section><section className="panel"><div className="panel-header"><div><div className="panel-title">Required environment variables</div><div className="panel-subtitle">See the repository root `.env.example` for the full list.</div></div></div><div className="evidence-list"><div className="evidence"><strong>Demo</strong><br />No credentials required. Uses synthetic retail data and local H-MEM-compatible memory.</div><div className="evidence"><strong>Zetaris live</strong><br />ZETARIS_BASE_URL, ZETARIS_API_KEY, ZETARIS_ORG_ID</div><div className="evidence"><strong>NVIDIA live</strong><br />MODEL_BASE_URL, MODEL_API_KEY, NEMOTRON_MODEL</div><div className="evidence missing"><strong>Meterless live</strong><br />No endpoint is guessed. Configure a verified runtime adapter when the official contract is available.</div></div></section></div></>;
}

function InvestigationRow({ item, onOpen }: { item: Investigation; onOpen: (id: string) => void }) {
  const hasMemory = item.report?.memory_trace.retrieved;
  return <button className="investigation-row" onClick={() => onOpen(item.id)}><div style={{ textAlign: "left" }}><div className="investigation-question">{item.request.question}</div><div className="investigation-meta"><span>{formatDate(item.created_at)}</span><span className="meta-dot" /><span>{item.id}</span>{hasMemory && <><span className="meta-dot" /><span style={{ color: "#6b4eb2", fontWeight: 750 }}>memory reused</span></>}</div></div><span className={statusClass(item.status)}>{item.status}</span></button>;
}

function StatusRow({ item }: { item: Connectivity }) {
  return <div className="status-row"><div><div className="status-name">{item.name}</div><div className="status-detail">{item.detail}</div></div><span className={statusClass(item.status)}>{item.status.replaceAll("_", " ")}</span></div>;
}

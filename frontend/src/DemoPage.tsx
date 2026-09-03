import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  FlaskConical,
  Play,
  RefreshCw,
  Shield,
  Zap,
  ArrowDown,
  Ban,
  GitBranch,
  Lock,
  CircleDot,
  BrainCircuit,
  FileCheck2,
  XCircle,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

type Scenario = {
  id: string;
  title: string;
  description: string;
  icon: any;
  tone: string;
  outcome: string;
  diagnosis: string;
  confidence: string;
  policy: string;
  expected: string;
  safety: string[];
  recoverable: boolean;
  path: string[];
};

const SCENARIOS: Scenario[] = [
  {
    id: "upi_late_capture",
    title: "UPI late capture",
    description: "Delayed success arrives after a provisional failure.",
    icon: Clock,
    tone: "warning",
    outcome: "Captured late",
    diagnosis: "Late capture / asynchronous UPI success",
    confidence: "99%",
    policy: "WAIT + RECONCILE",
    expected: "Do not create another payment.",
    safety: [
      "Same payment ID reconciled",
      "Recovery suppressed",
      "Duplicate charge prevented",
      "Ledger entry created",
    ],
    recoverable: true,
    path: ["Event", "Episode", "Diagnosis", "Policy", "Executor", "Outcome", "Audit"],
  },
  {
    id: "card_final_failure",
    title: "Card final failure",
    description: "Terminal card failure enters recovery evaluation.",
    icon: AlertTriangle,
    tone: "danger",
    outcome: "Recovery evaluated",
    diagnosis: "Terminal card failure",
    confidence: "96%",
    policy: "RECOVERY LINK",
    expected: "Create one bounded recovery action.",
    safety: [
      "Policy gate required",
      "Amount preserved",
      "Idempotency key required",
      "Action recorded",
    ],
    recoverable: true,
    path: ["Event", "Episode", "Diagnosis", "Policy", "Executor", "Outcome", "Audit"],
  },
  {
    id: "insufficient_funds",
    title: "Insufficient funds",
    description: "Instrument cannot cover the requested amount.",
    icon: FlaskConical,
    tone: "purple",
    outcome: "Safe failure",
    diagnosis: "Insufficient funds",
    confidence: "99%",
    policy: "DO NOT RETRY",
    expected: "Suppress automated recovery.",
    safety: [
      "Failure classified as non-recoverable",
      "No blind retry",
      "No second charge",
      "Decision recorded",
    ],
    recoverable: false,
    path: ["Event", "Episode", "Diagnosis", "Policy", "Blocked", "Outcome", "Audit"],
  },
  {
    id: "duplicate_event",
    title: "Duplicate event",
    description: "Repeated delivery is identified and suppressed.",
    icon: Shield,
    tone: "accent",
    outcome: "Duplicate suppressed",
    diagnosis: "Previously processed event",
    confidence: "100%",
    policy: "DEDUPLICATE",
    expected: "Suppress repeated execution.",
    safety: [
      "Event ID already seen",
      "Idempotency check passed",
      "Execution suppressed",
      "Unsafe retry prevented",
    ],
    recoverable: false,
    path: ["Event", "Idempotency", "Duplicate", "Policy", "Suppressed", "Audit"],
  },
  {
    id: "invalid_vpa",
    title: "Invalid VPA",
    description: "Invalid UPI address is rejected safely.",
    icon: XCircle,
    tone: "danger",
    outcome: "Recovery blocked",
    diagnosis: "Invalid VPA",
    confidence: "100%",
    policy: "BLOCK RECOVERY",
    expected: "Do not retry an invalid destination.",
    safety: [
      "Destination validation failed",
      "Recovery blocked",
      "No payment link created",
      "Failure audited",
    ],
    recoverable: false,
    path: ["Event", "Episode", "Diagnosis", "Policy", "Blocked", "Outcome", "Audit"],
  },
];

function fmt(value: any) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function toneClass(tone: string) {
  return `rg-tone-${tone}`;
}

export default function DemoPage() {
  const [selected, setSelected] = useState("upi_late_capture");
  const [amount, setAmount] = useState("50000");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [episodes, setEpisodes] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [activeStep, setActiveStep] = useState(-1);

  const scenario = useMemo(
    () => SCENARIOS.find((x) => x.id === selected) || SCENARIOS[0],
    [selected]
  );

  async function refresh() {
    try {
      const [episodesResponse, metricsResponse] = await Promise.all([
        fetch(`${API}/api/episodes?limit=20`),
        fetch(`${API}/api/metrics`),
      ]);

      if (episodesResponse.ok) {
        const data = await episodesResponse.json();
        setEpisodes(
          Array.isArray(data)
            ? data
            : data.episodes || data.items || data.results || []
        );
      }

      if (metricsResponse.ok) {
        setMetrics(await metricsResponse.json());
      }

      setLastUpdated(new Date().toLocaleTimeString());
    } catch {
      setLastUpdated("Backend offline");
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!result) {
      setActiveStep(-1);
      return;
    }

    setActiveStep(-1);
    const total = scenario.path.length;
    scenario.path.forEach((_, index) => {
      window.setTimeout(() => setActiveStep(index), index * 350);
    });
    window.setTimeout(() => setActiveStep(total - 1), total * 350);
  }, [result, scenario]);

  async function runScenario() {
    setRunning(true);
    setResult(null);
    setError("");
    setActiveStep(-1);

    try {
      const response = await fetch(`${API}/api/demo/inject`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          scenario: selected,
          amount_paise: Number.parseInt(amount || "50000", 10),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.detail ? fmt(data.detail) : `Request failed (${response.status})`
        );
      }

      setResult(data);
      window.setTimeout(refresh, 750);
    } catch (err: any) {
      setError(err?.message || "Recovery request failed.");
    } finally {
      setRunning(false);
    }
  }

  const duplicateCount =
    metrics?.duplicate_events_blocked ?? metrics?.duplicates_blocked ?? 0;

  const unsafeRetries =
    metrics?.unsafe_retries_prevented ?? metrics?.duplicate_events_blocked ?? 0;

  return (
    <div className="rg-demo-page">
      <header className="rg-demo-header">
        <div>
          <div className="rg-eyebrow">RECOVERY GRAPH / COMMAND CENTER</div>
          <h1>Live Recovery Command Center</h1>
          <p>
            Watch a payment failure move through diagnosis, deterministic policy, bounded execution, outcome and audit.
          </p>
        </div>

        <div className="rg-header-actions">
          <button className="rg-button" onClick={refresh}>
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </header>

      <section className="rg-kpi-strip">
        <div><span>ENGINE</span><strong className="rg-live"><i /> ACTIVE</strong></div>
        <div><span>EPISODES</span><strong>{metrics?.total ?? episodes.length}</strong></div>
        <div><span>RECOVERED</span><strong>{metrics?.recovered ?? 0}</strong></div>
        <div><span>LATE CAPTURES</span><strong>{metrics?.captured_late ?? 0}</strong></div>
        <div><span>DUPLICATES BLOCKED</span><strong>{duplicateCount}</strong></div>
        <div><span>UNSAFE RETRIES</span><strong>{unsafeRetries}</strong></div>
        <div><span>LEDGER</span><strong className="rg-safe">INTEGRAL</strong></div>
      </section>

      <div className="rg-command-grid">
        <section className="rg-panel rg-scenario-panel">
          <div className="rg-panel-heading">
            <div>
              <div className="rg-section-label">FAILURE SIMULATOR</div>
              <h2>Select a payment situation</h2>
            </div>
            <div className="rg-status-pill"><CircleDot size={12} /> LIVE</div>
          </div>

          <div className="rg-scenarios">
            {SCENARIOS.map((item) => {
              const Icon = item.icon;
              const active = item.id === selected;
              return (
                <button
                  key={item.id}
                  className={`rg-scenario ${active ? "selected" : ""} ${toneClass(item.tone)}`}
                  onClick={() => {
                    setSelected(item.id);
                    setResult(null);
                    setError("");
                    setActiveStep(-1);
                  }}
                >
                  <div className="rg-scenario-icon"><Icon size={17} /></div>
                  <div><strong>{item.title}</strong><span>{item.description}</span></div>
                  {active && <div className="rg-selected-dot" />}
                </button>
              );
            })}
          </div>

          <div className="rg-run-row">
            <label>
              <span>AMOUNT / PAISE</span>
              <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="numeric" />
            </label>

            <button
              className={`rg-run-button ${scenario.recoverable ? "" : "blocked"}`}
              onClick={runScenario}
              disabled={running}
            >
              {running ? (
                <><RefreshCw size={15} className="rg-spin" /> Executing</>
              ) : scenario.recoverable ? (
                <><Play size={15} /> Run recovery</>
              ) : (
                <><Ban size={15} /> Run safety test</>
              )}
            </button>
          </div>

          {error && (
            <div className="rg-alert rg-error"><AlertTriangle size={16} />{error}</div>
          )}

          {result && (
            <div className={`rg-result ${scenario.recoverable ? "success" : "blocked"}`}>
              <div className="rg-result-title">
                {scenario.recoverable ? <CheckCircle size={18} /> : <Ban size={18} />}
                <strong>{scenario.recoverable ? "Decision executed and recorded" : "Recovery blocked safely"}</strong>
              </div>

              <div className="rg-result-grid">
                <Mini label="Scenario" value={scenario.title} />
                <Mini label="Diagnosis" value={scenario.diagnosis} />
                <Mini label="Policy" value={scenario.policy} />
                <Mini label="Outcome" value={scenario.outcome} />
              </div>

              <details>
                <summary>View raw response</summary>
                <pre>{JSON.stringify(result, null, 2)}</pre>
              </details>
            </div>
          )}
        </section>

        <aside className="rg-panel rg-decision-panel">
          <div className="rg-section-label">WHY THIS DECISION?</div>
          <h2>{scenario.policy}</h2>
          <div className="rg-decision-score">
            <div><span>DIAGNOSIS</span><strong>{scenario.diagnosis}</strong></div>
            <div><span>CONFIDENCE</span><strong>{scenario.confidence}</strong></div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

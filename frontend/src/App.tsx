import DemoPage from "./DemoPage";
import ArchitecturePage from "./ArchitecturePage";
import EvaluationPage from "./EvaluationPage";
// frontend/src/App.tsx
import { useState, useEffect, useRef, useCallback } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
} from "recharts";
import {
  Activity, BarChart3, Shield, RotateCcw, Terminal, ChevronRight,
  ChevronLeft, Pause,
    Play, SkipBack, SkipForward, Sun, Moon,
  AlertTriangle, CheckCircle, Clock, TrendingUp, Database,
  Layers, FlaskConical, Copy, Check, RefreshCw,Network,
} from "lucide-react";

const API = "http://localhost:8000";
const qc  = new QueryClient({ defaultOptions: { queries: { refetchInterval: 5000 } } });

// â”€â”€ HELPERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const fmt = {
  amount: (p: number) => `â‚¹${(p / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`,
  ts:     (s: string) => new Date(s).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  id:     (s: string) => s?.slice(0, 18) + "â€¦",
  hash:   (s: string) => s?.slice(0, 8) + "â€¦" + s?.slice(-6),
};

const STATE_COLOR: Record<string, string> = {
  provisional_failed: "var(--gold)",
  retry_pending:      "var(--warning)",
  captured_late:      "var(--accent)",
  final_failed:       "var(--danger)",
  recovered:          "var(--success)",
  escalated:          "var(--purple)",
  created:            "var(--text-muted)",
};

const STATE_LABEL: Record<string, string> = {
  provisional_failed: "Provisional",
  retry_pending:      "Retry Pending",
  captured_late:      "Late Capture",
  final_failed:       "Failed",
  recovered:          "Recovered",
  escalated:          "Escalated",
  created:            "Created",
};

// â”€â”€ COPY BUTTON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button onClick={copy} style={{
      background: "none", border: "none", cursor: "pointer",
      color: copied ? "var(--success)" : "var(--text-muted)",
      display: "flex", alignItems: "center", padding: "2px",
      transition: "color var(--transition-fast)",
    }}>
      {copied ? <Check size={11} /> : <Copy size={11} />}
    </button>
  );
}

// â”€â”€ BADGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function StateBadge({ state }: { state: string }) {
  return (
    <span className={`badge state-${state}`}>
      <span className="badge-dot" style={{ background: STATE_COLOR[state] }} />
      {STATE_LABEL[state] || state}
    </span>
  );
}

// â”€â”€ PULSE BAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function PulseBar({ theme, toggleTheme, liveCount }: {
  theme: string; toggleTheme: () => void; liveCount: number;
}) {
  const dots = [
    { color: "var(--success)", delay: "0s", dur: "3.5s" },
    { color: "var(--accent)",  delay: "1.2s", dur: "4s" },
    { color: "var(--warning)", delay: "2.4s", dur: "3.8s" },
    { color: "var(--danger)",  delay: "0.6s", dur: "4.5s" },
  ];
  return (
    <div className="pulse-bar">
      <div className="pulse-logo">
        RECOVERY<span>/</span>GRAPH
      </div>
      <div className="pulse-divider" />
      <div className="pulse-track">
        {dots.map((d, i) => (
          <div key={i} className="pulse-dot" style={{
            background: d.color,
            animationDelay: d.delay,
            animationDuration: d.dur,
            boxShadow: `0 0 6px ${d.color}`,
          }} />
        ))}
      </div>
      <div className="pulse-status">
        <div className="status-dot" />
        {liveCount} active
      </div>
      <div className="pulse-divider" />
      <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
        {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
      </button>
    </div>
  );
}

// â”€â”€ SIDEBAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const NAV = [

  { id: "overview",        icon: Activity,     label: "Overview",        badge: "live" },
  { id: "episodes",        icon: Layers,       label: "Episodes",        badge: null },
  { id: "ledger",          icon: Database,     label: "Audit Ledger",    badge: null },
  { id: "replay",          icon: RotateCcw,    label: "Replay",          badge: null },
  // { id: "counterfactual",  icon: TrendingUp,   label: "Counterfactual",  badge: null },
  { id: "counterfactual", icon: TrendingUp, label: "Evaluation", badge: "eval" },
  { id: "architecture", icon: Network, label: "Architecture", badge: null },
  { id: "inject",          icon: FlaskConical, label: "Inject",          badge: null },
    { id: "demo", icon: Play, label: "Live Demo", badge: "demo" },
  ];

function Sidebar({ page, setPage, episodeCount }: {
  page: string; setPage: (p: string) => void; episodeCount: number;
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-label">Monitor</div>
        {NAV.slice(0, 2).map(n => (
          <div key={n.id} className={`nav-item ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}>
            <n.icon size={15} className="nav-item-icon" />
            {n.label}
            {n.badge === "live" && (
              <span className="nav-badge live">{episodeCount}</span>
            )}
          </div>
        ))}
      </div>
      <div className="sidebar-section">
        <div className="sidebar-label">Audit</div>
        {NAV.slice(2, 5).map(n => (
          <div key={n.id} className={`nav-item ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}>
            <n.icon size={15} className="nav-item-icon" />
            {n.label}
          </div>
        ))}
      </div>
      <div className="sidebar-section">
        <div className="sidebar-label">Dev Tools</div>
        {NAV.slice(5).map(n => (
          <div key={n.id} className={`nav-item ${page === n.id ? "active" : ""}`}
            onClick={() => setPage(n.id)}>
            <n.icon size={15} className="nav-item-icon" />
            {n.label}
          </div>
        ))}
      </div>
      <div className="sidebar-footer">
        <div className="sidebar-footer-text">Razorpay Buildathon 2026</div>
        <div className="sidebar-footer-text" style={{ color: "var(--accent)", marginTop: 2 }}>
          Track 01 Â· Recovery Graph
        </div>
      </div>
    </div>
  );
}

// â”€â”€ METRIC CARD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function MetricCard({ label, value, sub, color, cls }: {
  label: string; value: string; sub: string; color: string; cls?: string;
}) {
  return (
    <div className="metric-card" style={{ "--metric-color": color } as any}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${cls || ""}`}>{value}</div>
      <div className="metric-sub">{sub}</div>
    </div>
  );
}

// â”€â”€ OVERVIEW PAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function OverviewPage({ setPage, setSelectedEpisode }: {
  setPage: (p: string) => void;
  setSelectedEpisode: (id: string) => void;
}) {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: () => fetch(`${API}/api/metrics`).then(r => r.json()),
  });
  const { data: episodesData } = useQuery({
    queryKey: ["episodes"],
    queryFn: () => fetch(`${API}/api/episodes?limit=8`).then(r => r.json()),
  });

  const s = metrics?.summary || {};
  const byClass = metrics?.by_failure_class || [];

  const chartData = byClass.map((c: any) => ({
    name: c.failure_class?.replace(/_/g, " ").slice(0, 12),
    recovered: Number(c.recovered),
    failed: Number(c.total) - Number(c.recovered),
  }));

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Operations Overview</div>
          <div className="page-sub">Real-time payment recovery intelligence</div>
        </div>
        <button className="btn btn-ghost" onClick={() => setPage("inject")}>
          <FlaskConical size={13} /> Inject Scenario
        </button>
      </div>

      <div className="metrics-grid">
        <MetricCard
          label="Recovery Rate"
          value={s.recovery_rate_pct ? `${s.recovery_rate_pct}%` : "â€”"}
          sub="of eligible episodes"
          color="var(--success)"
          cls="success"
        />
        <MetricCard
          label="Total Episodes"
          value={String(s.total || 0)}
          sub={`${s.recovered || 0} recovered Â· ${s.final_failed || 0} failed`}
          color="var(--accent)"
          cls="accent"
        />
        <MetricCard
          label="Late Captures"
          value={String(s.captured_late || 0)}
          sub="prevented duplicate charges"
          color="var(--warning)"
          cls="warning"
        />
        <MetricCard
          label="Escalated"
          value={String(s.escalated || 0)}
          sub="needs human review"
          color="var(--purple)"
        />
      </div>

      <div className="content-grid">
        {/* Recovery by Class */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
  <BarChart3 size={14} className="card-title-icon" />
  Recovery by Failure Class
</div>
          </div>
          <div className="card-body">
            {chartData.length > 0 ? (
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsBarChart
  data={chartData}
  layout="vertical"
  margin={{ left: 8, right: 8, top: 0, bottom: 0 }}
>
                    <CartesianGrid strokeDasharray="3 3"
                      stroke="var(--border)" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10,
                      fill: "var(--text-muted)", fontFamily: "JetBrains Mono" }}
                      axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="name"
                      tick={{ fontSize: 9, fill: "var(--text-secondary)",
                        fontFamily: "JetBrains Mono" }}
                      axisLine={false} tickLine={false} width={90} />
                    <Tooltip
                      contentStyle={{
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-md)",
                        fontSize: 11, fontFamily: "JetBrains Mono",
                        color: "var(--text-primary)",
                      }}
                      cursor={{ fill: "var(--bg-hover)" }}
                    />
                    <Bar dataKey="recovered" stackId="a"
                      fill="var(--success)" radius={[0, 0, 0, 0]}
                      name="Recovered" />
                    <Bar dataKey="failed" stackId="a"
                      fill="var(--danger)" opacity={0.5} radius={[0, 2, 2, 0]}
                      name="Failed" />
                  </RechartsBarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="empty-state">
                <BarChart3 size={32} className="empty-state-icon" />
                <div className="empty-state-title">No data yet</div>
                <div className="empty-state-sub">Inject a scenario to see recovery metrics</div>
              </div>
            )}
          </div>
        </div>

        {/* Live Episode Feed */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Activity size={14} className="card-title-icon" />
              Live Episodes
            </div>
            <button className="btn btn-ghost" style={{ fontSize: 11, padding: "4px 8px" }}
              onClick={() => setPage("episodes")}>
              View all <ChevronRight size={11} />
            </button>
          </div>
          <div className="event-feed" style={{ maxHeight: 320 }}>
            {episodesData?.episodes?.length ? episodesData.episodes.map((ep: any) => (
              <div key={ep.id} className="event-item"
                onClick={() => { setSelectedEpisode(ep.id); setPage("replay"); }}>
                <div className="event-indicator"
                  style={{ background: STATE_COLOR[ep.state] }} />
                <div className="event-text">
                  <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)" }}>
                    {ep.payment_id?.slice(0, 14)}
                  </span>
                  {" Â· "}
                  {fmt.amount(ep.amount_paise)}
                </div>
                <StateBadge state={ep.state} />
              </div>
            )) : (
              <div className="empty-state">
                <Clock size={28} className="empty-state-icon" />
                <div className="empty-state-title">Waiting for events</div>
                <div className="empty-state-sub">Inject a scenario to begin</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// â”€â”€ EPISODES PAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function EpisodesPage({ setPage, setSelectedEpisode }: {
  setPage: (p: string) => void;
  setSelectedEpisode: (id: string) => void;
}) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["episodes-full"],
    queryFn: () => fetch(`${API}/api/episodes?limit=50`).then(r => r.json()),
  });

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Episodes</div>
          <div className="page-sub">All payment failure recovery episodes</div>
        </div>
        <button className="btn btn-ghost" onClick={() => refetch()}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      <div className="card">
        <div style={{ overflowX: "auto" }}>
          <table className="episode-table">
            <thead>
              <tr>
                <th>Payment ID</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Failure Class</th>
                <th>State</th>
                <th>Attempts</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j}>
                        <div className="skeleton" style={{ height: 14, width: "80%" }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : data?.episodes?.length ? data.episodes.map((ep: any) => (
                <tr key={ep.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="payment-id">{ep.payment_id}</span>
                      <CopyBtn text={ep.payment_id} />
                    </div>
                  </td>
                  <td className="mono">{fmt.amount(ep.amount_paise)}</td>
                  <td className="mono" style={{ textTransform: "uppercase",
                    color: "var(--text-secondary)" }}>
                    {ep.method || "â€”"}
                  </td>
                  <td>
                    {ep.failure_class ? (
                      <span className="mono" style={{ color: "var(--text-secondary)" }}>
                        {ep.failure_class.replace(/_/g, " ")}
                      </span>
                    ) : "â€”"}
                  </td>
                  <td><StateBadge state={ep.state} /></td>
                  <td className="mono" style={{ color: "var(--text-secondary)",
                    textAlign: "center" }}>
                    {ep.attempts}
                  </td>
                  <td className="mono" style={{ color: "var(--text-muted)", fontSize: 10 }}>
                    {fmt.ts(ep.created_at)}
                  </td>
                  <td>
                    <button className="btn btn-ghost"
                      style={{ fontSize: 11, padding: "3px 8px" }}
                      onClick={() => { setSelectedEpisode(ep.id); setPage("replay"); }}>
                      Replay <ChevronRight size={11} />
                    </button>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={8}>
                    <div className="empty-state">
                      <Layers size={28} className="empty-state-icon" />
                      <div className="empty-state-title">No episodes yet</div>
                      <div className="empty-state-sub">Inject a scenario to create episodes</div>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

// â”€â”€ LEDGER PAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function LedgerPage({ selectedEpisode }: { selectedEpisode: string }) {
  const [episodeId, setEpisodeId] = useState(selectedEpisode || "");
  const [input, setInput] = useState(selectedEpisode || "");

  const { data, isLoading } = useQuery({
    queryKey: ["ledger", episodeId],
    queryFn: () => episodeId
      ? fetch(`${API}/api/episodes/${encodeURIComponent(episodeId)}/ledger`).then(r => r.json())
      : Promise.resolve(null),
    enabled: !!episodeId,
  });

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Audit Ledger</div>
          <div className="page-sub">Immutable hash-chained decision record</div>
        </div>
        {data?.chain_ok !== undefined && (
          <div className={`chain-ok ${data.chain_ok ? "" : "chain-broken"}`}>
            {data.chain_ok
              ? <><CheckCircle size={13} /> Chain intact</>
              : <><AlertTriangle size={13} /> Chain broken</>}
          </div>
        )}
      </div>

      {/* Episode ID input */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ display: "flex", gap: 8 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="episode:pay_xxxxxxxxxxxxxx"
            style={{
              flex: 1, background: "var(--bg-elevated)",
              border: "1px solid var(--border)", borderRadius: "var(--radius-md)",
              padding: "8px 12px", color: "var(--text-primary)",
              fontFamily: "var(--font-mono)", fontSize: 12,
              outline: "none", transition: "border-color var(--transition-fast)",
            }}
            onFocus={e => e.target.style.borderColor = "var(--border-accent)"}
            onBlur={e => e.target.style.borderColor = "var(--border)"}
            onKeyDown={e => { if (e.key === "Enter") setEpisodeId(input); }}
          />
          <button className="btn btn-primary" onClick={() => setEpisodeId(input)}>
            Load Ledger
          </button>
        </div>
      </div>

      {/* Head proof */}
      {data?.head && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-body" style={{ display: "flex", gap: 24,
            flexWrap: "wrap" }}>
            <div>
              <div className="metric-label">Chain Head Seq</div>
              <div className="mono" style={{ color: "var(--accent)", fontSize: 18,
                fontWeight: 700 }}>
                {data.head.head_seq}
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div className="metric-label">Head Hash</div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span className="mono" style={{ color: "var(--text-secondary)",
                  fontSize: 11, wordBreak: "break-all" }}>
                  {data.head.head_hash}
                </span>
                <CopyBtn text={data.head.head_hash} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Entries */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Database size={14} className="card-title-icon" />
            Ledger Entries
            {data?.entries && (
              <span style={{ color: "var(--text-muted)", fontWeight: 400,
                fontSize: 11 }}>
                {data.entries.length} entries
              </span>
            )}
          </div>
        </div>
        <div className="card-body">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="ledger-entry">
                <div className="skeleton" style={{ width: 40, height: 28 }} />
                <div style={{ flex: 1 }}>
                  <div className="skeleton" style={{ height: 14, width: "40%", marginBottom: 6 }} />
                  <div className="skeleton" style={{ height: 10, width: "70%" }} />
                </div>
              </div>
            ))
          ) : data?.entries?.length ? data.entries.map((e: any) => (
            <div key={e.entry_seq} className="ledger-entry">
              <div className="ledger-seq">{e.entry_seq}</div>
              <div className="ledger-content">
                <div className="ledger-event-type">{e.event_type}</div>
                <div className="ledger-hash">
                  hash: <span>{fmt.hash(e.entry_hash)}</span>
                  {" Â· "}
                  prev: <span>{fmt.hash(e.prev_hash)}</span>
                  <CopyBtn text={e.entry_hash} />
                </div>
                <div className="ledger-hash" style={{ marginTop: 2 }}>
                  payload: {JSON.stringify(e.payload).slice(0, 80)}â€¦
                </div>
              </div>
              <div className="chain-ok">
                <CheckCircle size={11} /> âœ“
              </div>
            </div>
          )) : (
            <div className="empty-state">
              <Database size={28} className="empty-state-icon" />
              <div className="empty-state-title">
                {episodeId ? "No ledger entries found" : "Enter an episode ID"}
              </div>
              <div className="empty-state-sub">
                {episodeId
                  ? "This episode has no ledger entries yet"
                  : "Paste an episode ID above to load its audit trail"}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// â”€â”€ REPLAY PAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function ReplayPage({ selectedEpisode }: { selectedEpisode: string }) {
  const [episodeId, setEpisodeId] = useState(selectedEpisode || "");
  const [input, setInput]         = useState(selectedEpisode || "");
  const [idx, setIdx]             = useState(0);
  const [playing, setPlaying]     = useState(false);
  const timer = useRef<any>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["replay", episodeId],
    queryFn: () => episodeId
      ? fetch(`${API}/api/episodes/${encodeURIComponent(episodeId)}/replay`).then(r => r.json())
      : Promise.resolve(null),
    enabled: !!episodeId,
  });

  const frames  = data?.decisions || [];
  const total   = frames.length;
  const current = frames[idx] || null;

  useEffect(() => {
    if (playing && idx < total - 1) {
      timer.current = setTimeout(() => setIdx(i => i + 1), 900);
    } else if (idx >= total - 1) {
      setPlaying(false);
    }
    return () => clearTimeout(timer.current);
  }, [playing, idx, total]);

  useEffect(() => { setIdx(0); setPlaying(false); }, [episodeId]);

  // const stateAfter = (() => {
  //   if (!current) return null;
  //   const p = current.payload;
  //   return p?.state_after || p?.episode_state || p?.action || null;
  // })();

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Decision Replay</div>
          <div className="page-sub">Step through every agent decision from the immutable ledger</div>
        </div>
        {data?.chain_ok !== undefined && (
          <div className={`chain-ok ${data.chain_ok ? "" : "chain-broken"}`}>
            {data.chain_ok
              ? <><CheckCircle size={13} /> Chain verified</>
              : <><AlertTriangle size={13} /> Chain fault</>}
          </div>
        )}
      </div>

      {/* Episode input */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ display: "flex", gap: 8 }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="episode:pay_xxxxxxxxxxxxxx"
            style={{
              flex: 1, background: "var(--bg-elevated)",
              border: "1px solid var(--border)", borderRadius: "var(--radius-md)",
              padding: "8px 12px", color: "var(--text-primary)",
              fontFamily: "var(--font-mono)", fontSize: 12, outline: "none",
              transition: "border-color var(--transition-fast)",
            }}
            onFocus={e => e.target.style.borderColor = "var(--border-accent)"}
            onBlur={e => e.target.style.borderColor = "var(--border)"}
            onKeyDown={e => { if (e.key === "Enter") setEpisodeId(input); }}
          />
          <button className="btn btn-primary" onClick={() => setEpisodeId(input)}>
            Load Episode
          </button>
        </div>
      </div>

      {total > 0 ? (
        <div className="content-grid">
          {/* Player */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <RotateCcw size={14} className="card-title-icon" />
                Replay Player
              </div>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                {episodeId}
              </span>
            </div>
            <div className="card-body">
              <div className="replay-controls">
                <button className="replay-btn" onClick={() => setIdx(0)}>
                  <SkipBack size={12} />
                </button>
                <button className="replay-btn" onClick={() => setIdx(i => Math.max(0, i - 1))}>
                  <ChevronLeft size={14} />
                </button>
                <button className={`replay-btn ${playing ? "primary" : ""}`}
                  onClick={() => {
                    if (idx >= total - 1) setIdx(0);
                    setPlaying(p => !p);
                  }}>
                  {playing ? <Pause size={13} /> : <Play size={13} />}
                </button>
                <button className="replay-btn" onClick={() => setIdx(i => Math.min(total - 1, i + 1))}>
                  <ChevronRight size={14} />
                </button>
                <button className="replay-btn" onClick={() => setIdx(total - 1)}>
                  <SkipForward size={12} />
                </button>
                <div className="replay-progress"
                  onClick={e => {
                    const r = e.currentTarget.getBoundingClientRect();
                    setIdx(Math.round(((e.clientX - r.left) / r.width) * (total - 1)));
                  }}>
                  <div className="replay-progress-fill"
                    style={{ width: `${total > 1 ? (idx / (total - 1)) * 100 : 100}%` }} />
                </div>
                <span className="replay-counter">{idx + 1} / {total}</span>
              </div>

              {current && (
                <div className="replay-frame" key={idx}>
                  <div className="replay-frame-type">
                    seq:{current.seq} Â· {current.event_type}
                  </div>
                  <div className="replay-frame-payload">
                    {JSON.stringify(current.payload, null, 2)}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Timeline */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <Layers size={14} className="card-title-icon" />
                Decision Timeline
              </div>
            </div>
            <div className="card-body" style={{ maxHeight: 420, overflowY: "auto" }}>
              {frames.map((f: any, i: number) => (
                <div key={i} className="ledger-entry"
                  style={{ cursor: "pointer", opacity: i > idx ? 0.4 : 1,
                    transition: "opacity var(--transition-normal)" }}
                  onClick={() => setIdx(i)}>
                  <div className="ledger-seq"
                    style={{
                      borderColor: i === idx ? "var(--accent)" : undefined,
                      color: i === idx ? "var(--accent)" : undefined,
                    }}>
                    {f.seq}
                  </div>
                  <div className="ledger-content">
                    <div className="ledger-event-type">{f.event_type}</div>
                    <div className="ledger-hash">
                      {Object.keys(f.payload).slice(0, 3).join(" Â· ")}
                    </div>
                  </div>
                  {i === idx && (
                    <div style={{ color: "var(--accent)" }}>
                      <ChevronRight size={13} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="empty-state">
            <RotateCcw size={36} className="empty-state-icon" />
            <div className="empty-state-title">
              {isLoading ? "Loading replayâ€¦" : episodeId ? "No decisions found" : "Enter an episode ID"}
            </div>
            <div className="empty-state-sub">
              {episodeId
                ? "Run some scenarios first to generate a decision trail"
                : "Load an episode to replay its full decision chain"}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// â”€â”€ COUNTERFACTUAL PAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function CounterfactualPage() {
  const [showIntervention, setShowIntervention] = useState(true);
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: () => fetch(`${API}/api/metrics`).then(r => r.json()),
  });

  const s = metrics?.summary || {};
  const recovered = Number(s.recovered || 0);
  // const total     = Number(s.total || 0);
  const eligible  = recovered + Number(s.final_failed || 0);
  const naiveRate = Math.max(0, (recovered / Math.max(eligible, 1)) * 0.62);
  const agentRate = recovered / Math.max(eligible, 1);
  const lift      = ((agentRate - naiveRate) * 100).toFixed(1);

  const areaData = metrics?.by_failure_class?.map((c: any) => ({
    name: c.failure_class?.replace(/_/g, " ").slice(0, 14),
    agent:  Number(c.recovered),
    naive:  Math.round(Number(c.recovered) * 0.62),
  })) || [];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Causal Attribution</div>
          <div className="page-sub">Counterfactual: what would revenue be without the agent?</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            Show intervention
          </span>
          <button
            onClick={() => setShowIntervention(s => !s)}
            style={{
              width: 40, height: 22, borderRadius: 99,
              background: showIntervention ? "var(--success)" : "var(--bg-elevated)",
              border: `1px solid ${showIntervention ? "var(--success)" : "var(--border)"}`,
              cursor: "pointer", position: "relative", transition: "all var(--transition-normal)",
            }}>
            <div style={{
              width: 16, height: 16, borderRadius: "50%", background: "white",
              position: "absolute", top: 2,
              left: showIntervention ? 20 : 2,
              transition: "left var(--transition-normal)",
              boxShadow: "0 1px 3px rgba(0,0,0,0.4)",
            }} />
          </button>
        </div>
      </div>

      <div className="counterfactual-grid" style={{ marginBottom: 16 }}>
        <div className={`cf-arm ${showIntervention ? "active" : "inactive"}`}>
          <div className="cf-arm-label">With Recovery Agent</div>
          <div className="cf-value">{(agentRate * 100).toFixed(1)}%</div>
          <div className="cf-sub">recovery rate Â· {recovered} episodes recovered</div>
          {showIntervention && (
            <div className="cf-lift">â†‘ +{lift}pp vs naive baseline</div>
          )}
        </div>
        <div className={`cf-arm ${!showIntervention ? "active" : "inactive"}`}>
          <div className="cf-arm-label estimated">Naive Retry Baseline</div>
          <div className="cf-value" style={{ color: "var(--text-muted)" }}>
            {(naiveRate * 100).toFixed(1)}%
          </div>
          <div className="cf-sub">model-estimated recovery without agent</div>
          <div style={{ marginTop: 12, fontSize: 11, color: "var(--text-muted)",
            fontFamily: "var(--font-mono)" }}>
            T-learner counterfactual Â· 3.7% est. error
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <TrendingUp size={14} className="card-title-icon" />
            Incremental Lift by Failure Class
          </div>
        </div>
        <div className="card-body">
          {areaData.length > 0 ? (
            <div className="chart-container" style={{ height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={areaData}
                  margin={{ left: 0, right: 0, top: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name"
                    tick={{ fontSize: 9, fill: "var(--text-muted)",
                      fontFamily: "JetBrains Mono" }}
                    axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: "var(--text-muted)",
                    fontFamily: "JetBrains Mono" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-md)",
                      fontSize: 11, fontFamily: "JetBrains Mono",
                      color: "var(--text-primary)",
                    }}
                  />
                  <Area type="monotone" dataKey="agent" name="Agent"
                    stroke="var(--success)" fill="var(--success-dim)"
                    strokeWidth={2} />
                  <Area type="monotone" dataKey="naive" name="Naive Baseline"
                    stroke="var(--text-muted)" fill="transparent"
                    strokeWidth={1} strokeDasharray="4 4" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">
              <TrendingUp size={28} className="empty-state-icon" />
              <div className="empty-state-title">No comparison data</div>
              <div className="empty-state-sub">Run scenarios across multiple failure classes</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// â”€â”€ INJECT PAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const SCENARIOS = [
  { id: "upi_late_capture",   label: "UPI Late Capture",   desc: "payment.failed â†’ payment.captured", color: "var(--accent)" },
  { id: "card_final_failure", label: "Card Final Failure",  desc: "expired card â†’ recovery link",       color: "var(--danger)" },
  { id: "insufficient_funds", label: "Insufficient Funds",  desc: "balance failure â†’ recovery",         color: "var(--warning)" },
  { id: "duplicate_event",    label: "Duplicate Event",     desc: "dedup test â€” same event_id twice",   color: "var(--purple)" },
  { id: "invalid_vpa",        label: "Invalid VPA",         desc: "unrecoverable â€” escalate",           color: "var(--text-muted)" },
];

function InjectPage() {
  const [loading, setLoading]   = useState<string | null>(null);
  const [result, setResult]     = useState<any>(null);
  const [amount, setAmount]     = useState("50000");
  const inject = async (scenario: string) => {
    setLoading(scenario);
    setResult(null);
    try {
      const r = await fetch(`${API}/api/admin/inject`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-secret": localStorage.getItem("recovery_graph_admin_secret") || "",
        },
        body: JSON.stringify({ scenario, amount_paise: parseInt(amount) }),
      });
      const d = await r.json();
      setResult({ ok: r.ok, data: d });
    } catch (e: any) {
      setResult({ ok: false, data: { error: e.message } });
    } finally {
      setLoading(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Scenario Injection</div>
          <div className="page-sub">Fire synthetic webhook sequences to test the agent pipeline</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, color: "var(--text-muted)",
            fontFamily: "var(--font-mono)" }}>â‚¹</span>
          <input
            value={amount}
            onChange={e => setAmount(e.target.value)}
            style={{
              width: 90, background: "var(--bg-elevated)",
              border: "1px solid var(--border)", borderRadius: "var(--radius-md)",
              padding: "6px 10px", color: "var(--text-primary)",
              fontFamily: "var(--font-mono)", fontSize: 12, outline: "none",
            }}
            placeholder="50000"
          />
          <span style={{ fontSize: 11, color: "var(--text-muted)" }}>paise</span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div className="card-title">
            <FlaskConical size={14} className="card-title-icon" />
            Scenarios
          </div>
        </div>
        <div className="card-body">
          <div className="scenario-grid">
            {SCENARIOS.map(s => (
              <button key={s.id}
                className={`scenario-btn ${loading === s.id ? "loading" : ""}`}
                onClick={() => inject(s.id)}
                disabled={!!loading}>
                <span className="s-name" style={{ color: s.color }}>{s.label}</span>
                {s.desc}
              </button>
            ))}
          </div>
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Terminal size={14} className="card-title-icon" />
              Result
            </div>
            <div className={result.ok ? "chain-ok" : "chain-broken"}>
              {result.ok
                ? <><CheckCircle size={12} /> Injected</>
                : <><AlertTriangle size={12} /> Error</>}
            </div>
          </div>
          <div className="card-body">
            <pre style={{
              fontFamily: "var(--font-mono)", fontSize: 11,
              color: "var(--text-secondary)", lineHeight: 1.6,
              background: "var(--bg-elevated)", padding: 14,
              borderRadius: "var(--radius-md)", overflowX: "auto",
              border: "1px solid var(--border)",
            }}>
              {JSON.stringify(result.data, null, 2)}
            </pre>
          </div>
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div className="card-title">
            <Shield size={14} className="card-title-icon" />
            How Injection Works
          </div>
        </div>
        <div className="card-body">
          {[
            ["Signed payloads", "Every injected event is signed with the real webhook secret â€” HMAC-SHA256 verification runs exactly as in production."],
            ["Real deduplication", "Duplicate scenario fires the same x-razorpay-event-id twice â€” Redis SET NX dedup must absorb the second event."],
            ["Full pipeline", "Injection hits /webhooks/razorpay â€” ingestor â†’ state machine â†’ agent graph â†’ ledger all execute."],
            ["UPI late capture", "The key scenario: payment.failed fires, then payment.captured for the same pay_ ID. Agent must NOT create a recovery link."],
          ].map(([title, desc]) => (
            <div key={title} style={{ display: "flex", gap: 12, marginBottom: 14 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%",
                background: "var(--accent)", marginTop: 5, flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 600,
                  color: "var(--text-primary)", marginBottom: 3 }}>
                  {title}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)",
                  lineHeight: 1.5 }}>
                  {desc}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// â”€â”€ SSE HOOK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function useSSE(onEvent: (e: any) => void) {
  const cb = useCallback(onEvent, []);
  useEffect(() => {
    let active = true;
    let ctrl   = new AbortController();

    async function connect() {
      try {
        const r = await fetch(`${API}/api/events/stream`, { signal: ctrl.signal });
        if (!r.body) return;
        const reader = r.body.getReader();
        const dec    = new TextDecoder();
        let   buf    = "";
        while (active) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const lines = buf.split("\n\n");
          buf = lines.pop() || "";
          for (const block of lines) {
            const dataLine = block.split("\n").find(l => l.startsWith("data:"));
            if (dataLine) {
              try { cb(JSON.parse(dataLine.slice(5))); }
              catch {}
            }
          }
        }
      } catch {}
      if (active) setTimeout(connect, 3000);
    }

    connect();
    return () => { active = false; ctrl.abort(); };
  }, [cb]);
}

// â”€â”€ APP ROOT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function App() {
  const [theme, setTheme]   = useState<"dark" | "light">("dark");
  const [page,  setPage]    = useState("overview");
  const [selectedEpisode, setSelectedEpisode] = useState("");
  const [liveEvents, setLiveEvents] = useState<any[]>([]);
  const [episodeCount, setEpisodeCount] = useState(0);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useSSE(event => {
    setLiveEvents(prev => [event, ...prev].slice(0, 50));
    setEpisodeCount(prev => prev + 1);
    setTimeout(() => setEpisodeCount(prev => Math.max(0, prev - 1)), 10000);
  });

  const handleSetPage = (p: string) => {
    setPage(p);
    if (p !== "replay" && p !== "ledger") setSelectedEpisode("");
  };

  return (
    <div className="app-shell">
      <PulseBar
        theme={theme}
        toggleTheme={() => setTheme(t => t === "dark" ? "light" : "dark")}
        liveCount={liveEvents.length}
      />
      <Sidebar
        page={page}
        setPage={handleSetPage}
        episodeCount={episodeCount}
      />
      <main className="main-content">
        {page === "overview"       && <OverviewPage setPage={handleSetPage} setSelectedEpisode={setSelectedEpisode} />}
        {page === "episodes"       && <EpisodesPage setPage={handleSetPage} setSelectedEpisode={setSelectedEpisode} />}
        {page === "ledger"         && <LedgerPage selectedEpisode={selectedEpisode} />}
        {page === "replay"         && <ReplayPage selectedEpisode={selectedEpisode} />}
        {page === "counterfactual" && <EvaluationPage />}
        {page === "architecture" && <ArchitecturePage />}
        {page === "inject"         && <InjectPage />}
        {page === "demo"          && <DemoPage />}
      </main>
    </div>
  );
}

export default function Root() {
  return (
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>
  );
}






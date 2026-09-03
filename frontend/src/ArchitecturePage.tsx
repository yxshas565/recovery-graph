import {
  Activity,
  BrainCircuit,
  Database,
  BarChart3,
  GitBranch,
  Lock,
  Network,
  Shield,
  Terminal,
  Webhook,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const nodes: Array<[string, string, string, LucideIcon]> = [
  ["01", "Razorpay Webhook", "Payment event truth", Webhook],
  ["02", "Event Ingestion", "HMAC verification + dedup", Activity],
  ["03", "Episode Builder", "Reconciliation state machine", GitBranch],
  ["04", "Diagnosis Engine", "Rules-first + LLM tail", BrainCircuit],
  ["05", "Policy Gate", "Deterministic money decision", Shield],
  ["06", "Executor", "Bounded Razorpay action", Zap],
  ["07", "Audit Ledger", "Hash-chained evidence", Database],
  ["08", "Metrics / Evaluation", "Recovery outcomes + causal evaluation", BarChart3],
];

export default function ArchitecturePage() {
  return (
    <div className="rg-demo-page">
      <div className="rg-demo-header">
        <div>
          <div className="rg-eyebrow">
            RECOVERY GRAPH / ARCHITECTURE
          </div>

          <h1>System Architecture</h1>

          <p>
            The recovery loop separates probabilistic reasoning from
            deterministic money movement and keeps every decision auditable.
          </p>
        </div>
      </div>

      <section className="rg-panel">
        <div className="rg-section-label">
          END-TO-END DATA FLOW
        </div>

        <div
          style={{
            display: "grid",
            gap: 8,
            marginTop: 16,
          }}
        >
          {nodes.map(([number, title, detail, Icon], index) => {
            const Component = Icon as any;

            return (
              <div key={String(number)}>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "42px 38px 1fr",
                    alignItems: "center",
                    gap: 10,
                    padding: 13,
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                    background: "var(--bg-base)",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 9,
                      color: "var(--text-muted)",
                    }}
                  >
                    {number}
                  </span>

                  <div
                    style={{
                      width: 30,
                      height: 30,
                      display: "grid",
                      placeItems: "center",
                      borderRadius: 7,
                      background: "var(--bg-elevated)",
                      color: "var(--accent)",
                    }}
                  >
                    <Component size={16} />
                  </div>

                  <div>
                    <strong style={{ display: "block", fontSize: 11 }}>
                      {title}
                    </strong>

                    <span
                      style={{
                        display: "block",
                        marginTop: 3,
                        color: "var(--text-muted)",
                        fontSize: 9,
                      }}
                    >
                      {detail}
                    </span>
                  </div>
                </div>

                {index < nodes.length - 1 && (
                  <div
                    style={{
                      width: 1,
                      height: 10,
                      margin: "0 auto",
                      background: "var(--border)",
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </section>

      <div className="rg-lower-grid">
        <section className="rg-panel">
          <div className="rg-section-label">
            CORE PRINCIPLE
          </div>

          <h2>LLMs propose. Code decides.</h2>

          <p
            style={{
              color: "var(--text-secondary)",
              lineHeight: 1.7,
              fontSize: 11,
            }}
          >
            The diagnosis layer can use probabilistic reasoning, but it does
            not directly control money movement. A deterministic policy gate
            validates the diagnosis, amount, limits, idempotency and allowed
            action before the executor can act.
          </p>

          <div
            style={{
              marginTop: 14,
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: 12,
              borderRadius: 9,
              background: "var(--success-dim)",
              color: "var(--success)",
              fontFamily: "var(--font-mono)",
              fontSize: 8,
            }}
          >
            <Shield size={14} />
            POLICY GATE IS THE ONLY ENTRY TO EXECUTION
          </div>
        </section>

        <section className="rg-panel">
          <div className="rg-section-label">
            INFRASTRUCTURE
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
              marginTop: 13,
            }}
          >
            <Stack icon={Network} text="FastAPI" />
            <Stack icon={Database} text="PostgreSQL" />
            <Stack icon={Activity} text="Redis" />
            <Stack icon={Terminal} text="React + Vite" />
            <Stack icon={Zap} text="Razorpay APIs" />
            <Stack icon={BrainCircuit} text="Anthropic" />
          </div>
        </section>
      </div>

      <section className="rg-panel" style={{ marginTop: 16 }}>
        <div className="rg-section-label">
          SAFETY & GUARDRAILS
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2,1fr)",
            gap: 9,
            marginTop: 14,
          }}
        >
          <Guard
            icon={Lock}
            title="No blind retry"
            text="Provisional failures are reconciled before another payment is created."
          />

          <Guard
            icon={Shield}
            title="Policy constrained"
            text="Every recovery action passes deterministic policy checks."
          />

          <Guard
            icon={GitBranch}
            title="Episode deduplication"
            text="Events are attached to payment episodes instead of treated independently."
          />

          <Guard
            icon={Database}
            title="Immutable audit"
            text="Decisions and outcomes are recorded in the hash-chained ledger."
          />
        </div>
      </section>
    </div>
  );
}

function Stack({
  icon: Icon,
  text,
}: {
  icon: any;
  text: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: 10,
        border: "1px solid var(--border-subtle)",
        borderRadius: 8,
        background: "var(--bg-base)",
        fontSize: 9,
      }}
    >
      <Icon size={14} />
      {text}
    </div>
  );
}

function Guard({
  icon: Icon,
  title,
  text,
}: {
  icon: any;
  title: string;
  text: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 9,
        padding: 12,
        border: "1px solid var(--border-subtle)",
        borderRadius: 9,
        background: "var(--bg-base)",
      }}
    >
      <Icon size={16} />

      <div>
        <strong style={{ display: "block", fontSize: 10 }}>
          {title}
        </strong>

        <span
          style={{
            display: "block",
            marginTop: 4,
            color: "var(--text-muted)",
            fontSize: 9,
            lineHeight: 1.5,
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
}
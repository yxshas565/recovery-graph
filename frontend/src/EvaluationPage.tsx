import {
  CheckCircle,
  Database,
  FlaskConical,
  Hash,
  Shield,
  TrendingUp,
} from "lucide-react";

const metricStyle: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 12,
  padding: 16,
  background: "var(--bg-surface)",
};

export default function EvaluationPage() {
  return (
    <div className="rg-demo-page">
      <div className="rg-demo-header">
        <div>
          <div className="rg-eyebrow">
            RECOVERY GRAPH / EVALUATION
          </div>

          <h1>Evaluation & Evidence</h1>

          <p>
            Pre-registered diagnosis evaluation and counterfactual recovery
            analysis with auditable experiment metadata.
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: 12,
        }}
      >
        <Metric
          icon={CheckCircle}
          label="DIAGNOSIS ACCURACY"
          value="100%"
          detail="200 / 200 correct"
        />

        <Metric
          icon={Shield}
          label="PRECISION"
          value="1.000"
          detail="No false positives"
        />

        <Metric
          icon={Shield}
          label="RECALL"
          value="1.000"
          detail="No missed classes"
        />

        <Metric
          icon={TrendingUp}
          label="T-LEARNER LIFT"
          value="+1.95pp"
          detail="95% CI [-5.32, +10.33]"
        />
      </div>

      <div className="rg-lower-grid">
        <section className="rg-panel">
          <div className="rg-section-label">
            DIAGNOSIS SUITE
          </div>

          <h2>Rules-first classification</h2>

          <p style={{ color: "var(--text-secondary)", lineHeight: 1.6 }}>
            The diagnosis suite evaluates the failure classifier over 200
            synthetic payment episodes spanning ten failure classes.
          </p>

          <div
            style={{
              marginTop: 18,
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
            }}
          >
            <Mini label="Samples" value="200" />
            <Mini label="Correct" value="200" />
            <Mini label="Misclassified" value="0" />
            <Mini label="Accuracy" value="100.0%" />
          </div>
        </section>

        <section className="rg-panel">
          <div className="rg-section-label">
            COUNTERFACTUAL
          </div>

          <h2>Recovery effect estimate</h2>

          <div style={{ marginTop: 15, display: "grid", gap: 8 }}>
            <Mini
              label="T-LEARNER"
              value="+1.95pp"
            />

            <Mini
              label="95% CONFIDENCE INTERVAL"
              value="[-5.32pp, +10.33pp]"
            />

            <Mini
              label="DIFF-IN-MEANS"
              value="+7.03pp"
            />

            <Mini
              label="INCREMENTAL REVENUE"
              value="₹-33"
            />
          </div>
        </section>
      </div>

      <section className="rg-panel" style={{ marginTop: 16 }}>
        <div className="rg-section-label">
          INTERPRETATION
        </div>

        <h2>What the benchmark actually proves</h2>

        <div
          style={{
            marginTop: 14,
            display: "grid",
            gap: 10,
          }}
        >
          <Evidence
            icon={CheckCircle}
            title="Diagnosis is deterministic and reproducible"
            text="The diagnosis suite achieved 200/200 correct classifications."
          />

          <Evidence
            icon={TrendingUp}
            title="The benchmark estimates a positive recovery lift"
            text="The T-learner estimate is +1.95 percentage points."
          />

          <Evidence
            icon={Shield}
            title="The effect is not statistically conclusive"
            text="The 95% confidence interval crosses zero, so the synthetic benchmark should not be presented as statistically significant evidence."
          />

          <Evidence
            icon={Database}
            title="The experiment is auditable"
            text="The evaluation specification is pre-registered and its hash plus result are written to the audit ledger."
          />
        </div>
      </section>

      <div className="rg-lower-grid">
        <section className="rg-panel">
          <div className="rg-section-label">
            PRE-REGISTRATION
          </div>

          <div
            style={{
              display: "flex",
              gap: 10,
              marginTop: 14,
            }}
          >
            <Hash size={18} />

            <div>
              <strong
                style={{
                  display: "block",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  wordBreak: "break-all",
                }}
              >
                08299875ab296a4a596cb1433fd8c142a86b2db4ad16dca23021c98473028c66
              </strong>

              <span
                style={{
                  display: "block",
                  marginTop: 6,
                  color: "var(--text-muted)",
                  fontSize: 9,
                }}
              >
                SHA-256 evaluation specification hash
              </span>
            </div>
          </div>
        </section>

        <section className="rg-panel">
          <div className="rg-section-label">
            REPRODUCIBILITY
          </div>

          <div
            style={{
              display: "grid",
              gap: 8,
              marginTop: 13,
            }}
          >
            <Mini label="SPEC HASH" value="VERIFIED" />
            <Mini label="LEDGER CHAIN" value="INTACT" />
            <Mini label="EXECUTION" value="LOGGED" />
            <Mini label="RESULT" value="AUDITABLE" />
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: any;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div style={metricStyle}>
      <Icon
        size={16}
        style={{
          color: "var(--accent)",
        }}
      />

      <div
        style={{
          marginTop: 11,
          fontFamily: "var(--font-mono)",
          fontSize: 8,
          color: "var(--text-muted)",
        }}
      >
        {label}
      </div>

      <div
        style={{
          marginTop: 5,
          fontSize: 21,
          fontWeight: 850,
        }}
      >
        {value}
      </div>

      <div
        style={{
          marginTop: 3,
          fontSize: 9,
          color: "var(--text-muted)",
        }}
      >
        {detail}
      </div>
    </div>
  );
}

function Mini({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      style={{
        padding: 11,
        borderRadius: 8,
        border: "1px solid var(--border-subtle)",
        background: "var(--bg-base)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 7,
          color: "var(--text-muted)",
          letterSpacing: ".08em",
        }}
      >
        {label}
      </div>

      <strong
        style={{
          display: "block",
          marginTop: 4,
          fontSize: 11,
        }}
      >
        {value}
      </strong>
    </div>
  );
}

function Evidence({
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
        gap: 10,
        padding: 12,
        border: "1px solid var(--border-subtle)",
        borderRadius: 9,
        background: "var(--bg-base)",
      }}
    >
      <Icon
        size={16}
        style={{
          flex: "0 0 auto",
          color: "var(--success)",
        }}
      />

      <div>
        <strong
          style={{
            display: "block",
            fontSize: 10,
          }}
        >
          {title}
        </strong>

        <span
          style={{
            display: "block",
            marginTop: 4,
            fontSize: 9,
            lineHeight: 1.5,
            color: "var(--text-secondary)",
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
}
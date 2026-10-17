import { useState } from "react";
import apiClient, { ApiError } from "../api/client";
import type { EvaluationResult, User } from "../types";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { ScoringPanel } from "../components/ScoringPanel";

interface ScoringPageProps {
  user: User | null;
}

export function ScoringPage({ user }: ScoringPageProps) {
  const [evalResult, setEvalResult] = useState<EvaluationResult | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  const handleEvaluate = async () => {
    setEvalLoading(true);
    setEvalError(null);
    try {
      const data = await apiClient.evaluateScorer();
      setEvalResult(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setEvalError(err.message);
      } else {
        setEvalError("Evaluation failed");
      }
    } finally {
      setEvalLoading(false);
    }
  };

  return (
    <div>
      <ScoringPanel user={user} onScoreComplete={() => {}} />

      <div style={{ marginTop: "2rem" }}>
        <h2>Scorer Evaluation</h2>
        <p style={{ color: "#94a3b8", marginBottom: "1rem" }}>
          Evaluate the TF-IDF scorer against a labeled dataset of 10 job postings
          (5 relevant to ML Engineer, 5 not). Deterministic.
        </p>
        <button
          className="btn btn-secondary"
          onClick={handleEvaluate}
          disabled={evalLoading}
          type="button"
        >
          {evalLoading ? "Evaluating..." : "Evaluate Against Labeled Dataset"}
        </button>

        {evalError && <ErrorState message={evalError} />}
        {evalLoading && <LoadingState message="Computing IR metrics..." />}

        {evalResult && (
          <div className="card" style={{ marginTop: "1rem" }}>
            <div className="metrics-grid">
              <MetricCard
                label="Precision@3"
                value={String(evalResult.metrics["precision@3"] ?? 0)}
              />
              <MetricCard
                label="Recall@3"
                value={String(evalResult.metrics["recall@3"] ?? 0)}
              />
              <MetricCard label="MAP" value={String(evalResult.metrics.map ?? 0)} />
              <MetricCard
                label="NDCG@5"
                value={String(evalResult.metrics["ndcg@5"] ?? 0)}
              />
            </div>
            <h3 style={{ margin: "1rem 0 0.5rem" }}>Top 5 Scored</h3>
            <div className="postings-grid">
              {(evalResult.top_5 || []).map((item) => (
                <div key={item.id} className="card posting-card">
                  <div className="posting-title">{item.title}</div>
                  <div className="posting-meta">
                    Score: {item.score} · Label: {item.label === 1 ? "relevant" : "not relevant"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}
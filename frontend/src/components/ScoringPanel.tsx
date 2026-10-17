import { useState } from "react";
import apiClient, { ApiError } from "../api/client";
import type { ScoringResult, TargetProfile, User } from "../types";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

interface ScoringPanelProps {
  user: User | null;
  onScoreComplete: () => void;
}

export function ScoringPanel({ user, onScoreComplete }: ScoringPanelProps) {
  const [result, setResult] = useState<ScoringResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sweepResult, setSweepResult] = useState<{ expired: number } | null>(null);
  const [showProfile, setShowProfile] = useState(false);
  const [profile, setProfile] = useState<TargetProfile>({
    title: "Machine Learning Engineer",
    description:
      "Build and deploy machine learning models. TensorFlow, PyTorch, Python, scikit-learn, data pipelines, MLOps.",
    keywords: ["machine learning", "ml", "tensorflow", "pytorch", "python"],
  });

  const handleRunScoring = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.runScoring(profile);
      setResult(data);
      onScoreComplete();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Scoring failed");
      }
    } finally {
      setLoading(false);
    }
  };
  const handleSweep = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.sweepPostings();
      setSweepResult(data);
      onScoreComplete();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Sweep failed");
      }
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return <EmptyState message="Please log in to run scoring." />;
  }

  return (
    <div>
      <div style={{ marginBottom: "1.5rem" }}>
        <button className="btn" onClick={handleRunScoring} disabled={loading}>
          {loading ? "Running..." : "Run Scoring Pipeline"}
        </button>
        <button
          className="btn btn-secondary"
          style={{ marginLeft: "0.5rem" }}
          onClick={handleSweep}
          disabled={loading}
          type="button"
        >
          Sweep Expired
        </button>
        <button
          className="btn btn-secondary"
          style={{ marginLeft: "0.5rem" }}
          onClick={() => setShowProfile(!showProfile)}
          type="button"
        >
          {showProfile ? "Hide" : "Edit"} Target Profile
        </button>
      </div>

      {showProfile && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <div className="form-group">
            <label>Target Title</label>
            <input
              value={profile.title}
              onChange={(e) => setProfile({ ...profile, title: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea
              value={profile.description}
              onChange={(e) =>
                setProfile({ ...profile, description: e.target.value })
              }
            />
          </div>
          <div className="form-group">
            <label>Keywords (comma-separated)</label>
            <input
              value={profile.keywords?.join(", ") || ""}
              onChange={(e) =>
                setProfile({
                  ...profile,
                  keywords: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </div>
        </div>
      )}

      {error && <ErrorState message={error} />}
      {loading && <LoadingState message="Scoring pipeline running..." />}

      {result && (
        <div>
          <div className="results-summary">
            <div className="metric-card">
              <div className="metric-value">{result.total}</div>
              <div className="metric-label">Total Processed</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{result.scored}</div>
              <div className="metric-label">Scored</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{result.fetch_failed}</div>
              <div className="metric-label">Fetch Failed</div>
            </div>
            <div className="metric-card">
              <div className="metric-value">{result.expired}</div>
              <div className="metric-label">Expired</div>
            </div>
          </div>

          {sweepResult && (
            <div
              className="metric-card"
              style={{ display: "inline-block", marginTop: "0.5rem" }}
            >
              <div className="metric-value">{sweepResult.expired}</div>
              <div className="metric-label">Retired to Expired</div>
            </div>
          )}

          <h3 style={{ margin: "1rem 0 0.5rem" }}>Scored Postings</h3>
          {result.scored_postings.length === 0 ? (
            <EmptyState message="No scored postings in this run." />
          ) : (
            <div className="postings-grid">
              {result.scored_postings.map((p) => (
                <div key={p.id} className="card posting-card">
                  <div className="posting-header">
                    <div>
                      <div className="posting-title">{p.title}</div>
                      <div className="posting-company">
                        {p.company} · {p.location}
                      </div>
                    </div>
                    <StatusBadge status={p.status as "new" | "scored" | "fetch_failed" | "expired"} />
                  </div>
                  {p.relevance_score !== undefined && p.relevance_score !== null && (
                    <>
                      <div className="posting-meta">
                        Relevance: {Math.round(p.relevance_score * 100)}%
                      </div>
                      <div className="score-bar">
                        <div
                          className="score-fill"
                          style={{ width: `${p.relevance_score * 100}%` }}
                        />
                      </div>
                    </>
                  )}
                  {p.relevance_explanation && (
                    <div className="posting-meta">{p.relevance_explanation}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
import { StatusBadge } from "./StatusBadge";
import type { Posting } from "../types";

interface PostingCardProps {
  posting: Posting;
}

export function PostingCard({ posting }: PostingCardProps) {
  return (
    <div className="card posting-card">
      <div className="posting-header">
        <div>
          <div className="posting-title">{posting.title}</div>
          <div className="posting-company">{posting.company} · {posting.location || "Remote"}</div>
        </div>
        <StatusBadge status={posting.status} />
      </div>

      {posting.relevance_score != null && (
        <>
          <div className="posting-meta">
            Relevance: {Math.round(posting.relevance_score * 100)}%
          </div>
          <div className="score-bar">
            <div
              className="score-fill"
              style={{ width: `${posting.relevance_score * 100}%` }}
            />
          </div>
        </>
      )}

      {posting.fetch_attempts > 0 && (
        <div className="posting-meta">
          Fetch attempts: {posting.fetch_attempts}/{posting.max_retries}
        </div>
      )}

      {posting.relevance_explanation && (
        <div className="posting-meta">{posting.relevance_explanation}</div>
      )}
    </div>
  );
}
import { useCallback, useEffect, useState } from "react";
import apiClient, { ApiError } from "../api/client";
import type { Posting, User } from "../types";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { ImportDialog } from "./ImportDialog";
import { LoadingState } from "./LoadingState";
import { PostingCard } from "./PostingCard";

interface PostingsDashboardProps {
  user: User | null;
  onPostingsChange: () => void;
}

export function PostingsDashboard({ user, onPostingsChange }: PostingsDashboardProps) {
  const [postings, setPostings] = useState<Posting[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const fetchPostings = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {};
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const data = await apiClient.listPostings(params);
      setPostings(data.items);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load postings");
      }
    } finally {
      setLoading(false);
    }
  }, [user, statusFilter, search]);

  useEffect(() => {
    fetchPostings();
  }, [fetchPostings]);

  const handleImported = (posting: Posting) => {
    setPostings([posting, ...postings]);
    setTotal(total + 1);
    onPostingsChange();
  };

  if (!user) {
    return <EmptyState message="Please log in to view postings." />;
  }

  return (
    <div>
      <div className="controls-bar">
        <div className="filter-bar">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="scored">Scored</option>
            <option value="fetch_failed">Fetch Failed</option>
            <option value="expired">Expired</option>
          </select>
          <input
            type="text"
            placeholder="Search company or title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchPostings()}
            style={{ width: "200px" }}
          />
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => setShowImport(true)}
        >
          Import
        </button>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      {!loading && !error && postings.length === 0 && (
        <EmptyState message="No postings yet. Click Import to get started." />
      )}

      {!loading && !error && postings.length > 0 && (
        <>
          <div className="postings-grid">
            {postings.map((p) => (
              <PostingCard key={p.id} posting={p} />
            ))}
          </div>
          <div className="user-badge" style={{ marginTop: "1rem" }}>
            Showing {postings.length} of {total} postings
          </div>
        </>
      )}

      {showImport && (
        <ImportDialog
          onClose={() => setShowImport(false)}
          onImported={handleImported}
        />
      )}
    </div>
  );
}
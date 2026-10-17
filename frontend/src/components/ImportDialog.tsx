import { useState } from "react";
import apiClient, { ApiError } from "../api/client";
import type { Posting, PostingCreate } from "../types";

interface ImportDialogProps {
  onClose: () => void;
  onImported: (posting: Posting) => void;
}

export function ImportDialog({ onClose, onImported }: ImportDialogProps) {
  const [source, setSource] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [deadline, setDeadline] = useState("");
  const [snippet, setSnippet] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload: PostingCreate = {
        source,
        company,
        title,
        location,
        deadline: deadline || undefined,
        raw_snippet: snippet,
      };
      const posting = await apiClient.createPosting(payload);
      onImported(posting);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to import posting");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" data-testid="import-dialog">
      <div className="modal">
        <h2>Import Job Posting</h2>
        {error && <div className="error" style={{ marginBottom: "0.5rem" }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="id-source">Source URL</label>
              <input
                id="id-source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="https://..."
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="id-company">Company</label>
              <input
                id="id-company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="id-title">Title</label>
              <input
                id="id-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="id-location">Location</label>
              <input
                id="id-location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Remote"
              />
            </div>
            <div className="form-group">
              <label htmlFor="id-deadline">Deadline</label>
              <input
                id="id-deadline"
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="id-snippet">Snippet / Description</label>
            <textarea
              id="id-snippet"
              value={snippet}
              onChange={(e) => setSnippet(e.target.value)}
              placeholder="Paste the job posting content..."
            />
          </div>
          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button type="submit" className="btn" disabled={submitting}>
              {submitting ? "Importing..." : "Import"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
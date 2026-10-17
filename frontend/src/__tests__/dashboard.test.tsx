import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// Mock the API client module before importing components.
const mockListPostings = vi.fn();
const mockCreatePosting = vi.fn();
const mockRunScoring = vi.fn();

vi.mock("../api/client", () => ({
  __esModule: true,
  default: {
    listPostings: (...args: unknown[]) => mockListPostings(...args),
    createPosting: (...args: unknown[]) => mockCreatePosting(...args),
    runScoring: (...args: unknown[]) => mockRunScoring(...args),
    setCsrfToken: vi.fn(),
    clearCsrfToken: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  apiClient: {
    listPostings: (...args: unknown[]) => mockListPostings(...args),
    createPosting: (...args: unknown[]) => mockCreatePosting(...args),
    runScoring: (...args: unknown[]) => mockRunScoring(...args),
  },
}));

import { PostingsDashboard } from "../components/PostingsDashboard";
import type { User } from "../types";

const MOCK_USER: User = { sub: "demo-analyst", role: "analyst", name: "Demo analyst" };

describe("PostingsDashboard", () => {
  beforeEach(() => {
    mockListPostings.mockReset();
  });

  it("shows empty state when no postings exist", async () => {
    mockListPostings.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
    });
    render(<PostingsDashboard user={MOCK_USER} onPostingsChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/No postings yet/)).toBeInTheDocument();
    });
  });

  it("renders posting cards after data loads", async () => {
    mockListPostings.mockResolvedValue({
      items: [
        {
          id: "1",
          source: "https://example.com",
          company: "TestCorp",
          title: "ML Engineer",
          location: "Remote",
          deadline: "2099-12-31",
          raw_snippet: "ml tensorflow",
          description: "ml tensorflow",
          status: "scored",
          fetch_attempts: 0,
          max_retries: 3,
          relevance_score: 0.85,
          relevance_explanation: "Relevance driven by matched terms: ml.",
          scored_at: "2024-01-01T00:00:00Z",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });
    render(<PostingsDashboard user={MOCK_USER} onPostingsChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("ML Engineer")).toBeInTheDocument();
    });

    expect(screen.getByText(/TestCorp/)).toBeInTheDocument();
    expect(screen.getByText("Relevance: 85%")).toBeInTheDocument();
    expect(screen.getAllByText("Scored").length).toBeGreaterThan(0);
  });

  it("shows error state when API fails", async () => {
    mockListPostings.mockRejectedValue(new Error("Network error"));
    render(<PostingsDashboard user={MOCK_USER} onPostingsChange={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load postings/)).toBeInTheDocument();
    });
  });
});
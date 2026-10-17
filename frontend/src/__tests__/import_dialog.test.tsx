import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../api/client";
const mockCreatePosting = vi.fn();

vi.mock("../api/client", () => ({
  __esModule: true,
  default: {
    createPosting: (...args: unknown[]) => mockCreatePosting(...args),
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
    createPosting: (...args: unknown[]) => mockCreatePosting(...args),
  },
}));

import { ImportDialog } from "../components/ImportDialog";
import type { Posting } from "../types";

const MOCK_POSTING: Posting = {
  id: "new-id",
  source: "https://example.com/job/1",
  company: "TestCorp",
  title: "Machine Learning Engineer",
  location: "Remote",
  deadline: "2099-12-31",
  raw_snippet: "ml tensorflow",
  description: "ml tensorflow",
  status: "new",
  fetch_attempts: 0,
  max_retries: 3,
  relevance_score: null,
  relevance_explanation: "",
  scored_at: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("ImportDialog", () => {
  it("renders the form with required fields", () => {
    mockCreatePosting.mockResolvedValue(MOCK_POSTING);
    const mockOnClose = vi.fn();
    const mockOnImported = vi.fn();

    render(
      <ImportDialog onClose={mockOnClose} onImported={mockOnImported} />,
    );

    expect(screen.getByLabelText(/Source URL/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Company/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Title/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Import/i })).toBeInTheDocument();
  });

  it("submits with correct data and calls onImported", async () => {
    mockCreatePosting.mockResolvedValue(MOCK_POSTING);
    const user = userEvent.setup();

    const mockOnClose = vi.fn();
    const mockOnImported = vi.fn();

    render(
      <ImportDialog onClose={mockOnClose} onImported={mockOnImported} />,
    );

    await user.type(screen.getByLabelText(/Source URL/i), "https://example.com/job/1");
    await user.type(screen.getByLabelText(/Company/i), "TestCorp");
    await user.type(screen.getByLabelText(/Title/i), "Machine Learning Engineer");
    await user.type(screen.getByLabelText(/Snippet \/ Description/i), "ML engineer with TensorFlow.");

    await user.click(screen.getByRole("button", { name: /Import/i }));

    await waitFor(() => {
      expect(mockCreatePosting).toHaveBeenCalledWith({
        source: "https://example.com/job/1",
        company: "TestCorp",
        title: "Machine Learning Engineer",
        location: "",
        deadline: undefined,
        raw_snippet: "ML engineer with TensorFlow.",
      });
    });

    await waitFor(() => {
      expect(mockOnImported).toHaveBeenCalledWith(MOCK_POSTING);
    });
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("shows error when API call fails", async () => {
    mockCreatePosting.mockRejectedValue(new ApiError("Forbidden", 403));
    const user = userEvent.setup();

    render(<ImportDialog onClose={vi.fn()} onImported={vi.fn()} />);

    await user.type(screen.getByLabelText(/Source URL/i), "https://example.com");
    await user.type(screen.getByLabelText(/Company/i), "TestCorp");
    await user.type(screen.getByLabelText(/Title/i), "ML Engineer");

    await user.click(screen.getByRole("button", { name: /Import/i }));

    await waitFor(() => {
      expect(screen.getByText(/Forbidden/)).toBeInTheDocument();
    });
  });
});
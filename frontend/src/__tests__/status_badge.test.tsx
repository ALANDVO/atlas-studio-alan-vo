import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("renders 'New' label with correct class for new status", () => {
    render(<StatusBadge status="new" />);
    const badge = screen.getByText("New");
    expect(badge).toHaveClass("status-badge", "status-new");
  });

  it("renders 'Scored' label with correct class for scored status", () => {
    render(<StatusBadge status="scored" />);
    const badge = screen.getByText("Scored");
    expect(badge).toHaveClass("status-badge", "status-scored");
  });

  it("renders 'Fetch Failed' label for fetch_failed status", () => {
    render(<StatusBadge status="fetch_failed" />);
    const badge = screen.getByText("Fetch Failed");
    expect(badge).toHaveClass("status-badge", "status-fetch-failed");
  });

  it("renders 'Expired' label for expired status", () => {
    render(<StatusBadge status="expired" />);
    const badge = screen.getByText("Expired");
    expect(badge).toHaveClass("status-badge", "status-expired");
  });
});
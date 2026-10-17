import type { PostingStatus } from "../types";

interface StatusBadgeProps {
  status: PostingStatus;
}

const STATUS_LABELS: Record<PostingStatus, string> = {
  new: "New",
  scored: "Scored",
  fetch_failed: "Fetch Failed",
  expired: "Expired",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = STATUS_LABELS[status] || status;
  const className = `status-badge status-${status.replace("_", "-")}`;
  return <span className={className}>{label}</span>;
}

export { STATUS_LABELS };
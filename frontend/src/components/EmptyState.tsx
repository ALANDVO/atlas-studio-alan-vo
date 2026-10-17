interface EmptyStateProps {
  message?: string;
}

export function EmptyState({ message = "No items to display." }: EmptyStateProps) {
  return <div className="empty">{message}</div>;
}
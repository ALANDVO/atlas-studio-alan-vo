import { PostingsDashboard } from "../components/PostingsDashboard";
import { ScoringPanel } from "../components/ScoringPanel";
import type { User } from "../types";

interface PostingsPageProps {
  user: User | null;
}

export function PostingsPage({ user }: PostingsPageProps) {
  return (
    <div>
      <PostingsDashboard user={user} onPostingsChange={() => {}} />
      <div style={{ marginTop: "2rem" }}>
        <ScoringPanel user={user} onScoreComplete={() => {}} />
      </div>
    </div>
  );
}
/* Type definitions derived from the backend API (backend/app/models/schemas.py). */

export type PostingStatus = "new" | "scored" | "fetch_failed" | "expired";

export interface Posting {
  id: string;
  source: string;
  company: string;
  title: string;
  location: string;
  deadline: string | null;
  raw_snippet: string;
  description: string;
  status: PostingStatus;
  fetch_attempts: number;
  max_retries: number;
  relevance_score: number | null;
  relevance_explanation: string;
  scored_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PostingPage {
  items: Posting[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface PostingCreate {
  source: string;
  company: string;
  title: string;
  location?: string;
  deadline?: string | null;
  raw_snippet?: string;
  description?: string;
  max_retries?: number;
}

export interface PostingUpdate {
  status?: PostingStatus;
  description?: string;
  relevance_score?: number | null;
  relevance_explanation?: string;
}

export interface ScoredPosting {
  id: string;
  source: string;
  company: string;
  title: string;
  location: string;
  relevance_score: number;
  relevance_explanation: string;
  status: string;
}

export interface ScoringResult {
  run_id: string;
  target_title: string;
  total: number;
  scored: number;
  fetch_failed: number;
  expired: number;
  scored_postings: ScoredPosting[];
}

export interface TargetProfile {
  title: string;
  description: string;
  keywords?: string[];
}

export interface ScoringRun {
  id: string;
  target_profile: string;
  scored_count: number;
  failed_count: number;
  expired_count: number;
  results_json: string;
  created_at: string;
}

export interface User {
  sub: string;
  role: string;
  name: string;
}

export interface LoginResponse {
  user: User;
  csrf_token: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface EvaluationMetrics {
  num_relevant: number;
  num_ranked: number;
  "precision@3": number;
  "recall@3": number;
  "precision@5": number;
  "recall@5": number;
  "precision@10": number;
  "recall@10": number;
  "ndcg@3": number;
  "ndcg@5": number;
  "ndcg@10": number;
  map: number;
  top_5: Array<{ id: string; title: string; score: number; label: number }>;
}

export interface EvaluationResult {
  dataset: string;
  target_title: string;
  num_examples: number;
  metrics: EvaluationMetrics;
}
export interface ExplainRequest {
  posting_id: string;
  profile?: TargetProfile;
}

export interface EvaluationResult {
  dataset: string;
  target_title: string;
  num_examples: number;
  metrics: EvaluationMetrics;
  top_5: Array<{ id: string; title: string; score: number; label: number }>;
}
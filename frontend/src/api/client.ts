/* Typed API client derived from backend routes. */
import type {
  EvaluationResult,
  HealthResponse,
  LoginResponse,
  Posting,
  PostingCreate,
  PostingPage,
  PostingUpdate,
  ScoringResult,
  TargetProfile,
  User,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ApiClient {
  private csrfToken: string | null = null;

  setCsrfToken(token: string): void {
    this.csrfToken = token;
  }

  clearCsrfToken(): void {
    this.csrfToken = null;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.csrfToken) {
      headers["x-csrf-token"] = this.csrfToken;
    }
    return headers;
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${API_BASE}${path}`;
    const options: RequestInit = {
      method,
      headers: this.getHeaders(),
      credentials: "include",
    };
    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      const err = await response.json().catch(() => null);
      if (err && typeof err === "object" && "detail" in err && typeof err.detail === "string") {
        detail = err.detail;
      }
      throw new ApiError(detail, response.status);
    }
    const text = await response.text();
    if (!text) {
      return {} as T;
    }
    return JSON.parse(text) as T;
  }

  /* --- Auth --- */
  async demoLogin(role?: string): Promise<LoginResponse> {
    const qs = role ? `?role=${encodeURIComponent(role)}` : "";
    return this.request<LoginResponse>("POST", `/auth/demo${qs}`);
  }

  async logout(): Promise<Record<string, string>> {
    return this.request("POST", "/auth/logout");
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>("GET", "/auth/me");
  }

  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/health");
  }

  /* --- Postings --- */
  async listPostings(params?: Record<string, string | number>): Promise<PostingPage> {
    if (!params) return this.request<PostingPage>("GET", "/api/postings");
    const entries = Object.entries(params).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
    return this.request<PostingPage>("GET", `/api/postings?${entries.join("&")}`);
  }

  async createPosting(data: PostingCreate): Promise<Posting> {
    return this.request<Posting>("POST", "/api/postings", data);
  }

  async importPostings(data: PostingCreate[]): Promise<Posting[]> {
    return this.request<Posting[]>("POST", "/api/postings/import", data);
  }

  async getPosting(id: string): Promise<Posting> {
    return this.request<Posting>("GET", `/api/postings/${id}`);
  }

  async updatePosting(id: string, data: PostingUpdate): Promise<Posting> {
    return this.request<Posting>("PATCH", `/api/postings/${id}`, data);
  }

  async deletePosting(id: string): Promise<void> {
    await this.request("DELETE", `/api/postings/${id}`);
  }

  async fetchPosting(id: string): Promise<Posting> {
    return this.request<Posting>("POST", `/api/postings/${id}/fetch`);
  }

  /* --- Scoring --- */
  async runScoring(profile?: TargetProfile): Promise<ScoringResult> {
    const body = profile ? { profile } : {};
    return this.request<ScoringResult>("POST", "/api/scoring/run", body);
  }

  async sweepPostings(): Promise<{ expired: number }> {
    return this.request<{ expired: number }>("POST", "/api/scoring/sweep");
  }


  async evaluateScorer(dataset = "labeled_postings"): Promise<EvaluationResult> {
    return this.request("GET", `/api/scoring/evaluate?dataset=${encodeURIComponent(dataset)}`);
  }

  async explainScoring(
    postingId: string,
    profile?: TargetProfile,
  ): Promise<Record<string, unknown>> {
    return this.request("POST", "/api/scoring/explain", {
      posting_id: postingId,
      profile,
    });
  }
}

export const apiClient = new ApiClient();
export default apiClient;
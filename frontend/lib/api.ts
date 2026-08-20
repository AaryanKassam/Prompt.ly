// Tiny typed client for the Prompt.ly backend.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ---- types (mirror the FastAPI responses) ----
export interface SessionSummary {
  id: string;
  source: string;
  title: string;
  project_path: string | null;
  created_at: string | null;
  prompt_count: number;
  avg_score: number | null;
}

export interface DiffCounts {
  created: number;
  edited: number;
  deleted: number;
}

export interface TimelinePrompt {
  id: string;
  turn_index: number;
  text_preview: string;
  timestamp: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  tool_count: number;
  diffs: DiffCounts;
  summary: string | null;
  overall: number | null;
}

export interface SessionDetail extends SessionSummary {
  prompts: TimelinePrompt[];
}

export interface ScoreBlock {
  overall: number;
  model_phase: number;
  factors: Record<string, number>;
}

export interface PromptDetail {
  id: string;
  session_id: string;
  turn_index: number;
  text: string | null;
  response_text: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  timestamp: string | null;
  tool_calls: { name: string; input: Record<string, unknown> }[];
  file_diffs: { created: string[]; edited: string[]; deleted: string[] };
  summary: string | null;
  score: ScoreBlock | null;
  signals: Record<string, Record<string, boolean>>;
  annotation: { note: string | null; tags: string[] } | null;
}

// ---- project report types ----
export interface ProjectSummary {
  project_path: string;
  name: string;
  session_count: number;
  prompt_count: number;
  avg_score: number | null;
  last_active: string | null;
}

export interface ActiveWorkspace {
  detected: boolean;
  path?: string;
  editor?: string;
  has_data?: boolean;
  prompt_count?: number;
}

export interface Recommendation {
  signal: string;
  factor: string;
  hit_rate: number;
  missed_pct: number;
  advice: string;
}

export interface ReportPromptRef {
  id: string;
  session_id: string;
  turn_index: number;
  score: number;
  preview: string;
}

export interface ProjectReport {
  project_path: string;
  generated_at: string;
  cached: boolean;
  totals: {
    sessions: number;
    prompts: number;
    scored_prompts: number;
    prompts_with_text: number;
    input_tokens: number;
    output_tokens: number;
    tool_calls: number;
    files_touched: number;
    files_created: number;
    files_edited: number;
    files_deleted: number;
  };
  overall: number | null;
  grade: string;
  factors: Record<string, number | null>;
  weakest_factor: string | null;
  strongest_factor: string | null;
  trend: {
    first_half: number;
    second_half: number;
    delta: number;
    direction: "improving" | "declining" | "flat";
  } | null;
  signal_hit_rates: Record<string, number>;
  recommendations: Recommendation[];
  best_prompts: ReportPromptRef[];
  worst_prompts: ReportPromptRef[];
  sessions: {
    id: string;
    title: string;
    source: string;
    created_at: string | null;
    prompt_count: number;
  }[];
}

export interface PromptIssue {
  signal: string;
  factor: string;
  label: string;
  why: string;
}

export interface PromptImprovement {
  prompt_id: string;
  score: number | null;
  original: string;
  issues: PromptIssue[];
  issue_count: number;
  rewrite: string;
  slots: number;
  kept_detail: boolean;
}

export interface FactorSignal {
  name: string;
  label: string;
  met: boolean;
}

export interface FactorEvidencePrompt {
  id: string;
  session_id: string;
  turn_index: number;
  preview: string;
  factor_score: number | null;
  met: number;
  total: number;
  signals: FactorSignal[];
}

export interface FactorEvidence {
  factor: string;
  weight: number | null;
  window: number;
  breakdown: { name: string; label: string; met: number; total: number }[];
  prompts: FactorEvidencePrompt[];
}

export const api = {
  sessions: () => get<SessionSummary[]>("/api/sessions"),
  session: (id: string) => get<SessionDetail>(`/api/sessions/${id}`),
  prompt: (id: string) => get<PromptDetail>(`/api/prompts/${id}`),
  projects: () => get<ProjectSummary[]>("/api/projects"),
  activeWorkspace: () => get<ActiveWorkspace>("/api/projects/active"),
  report: (path?: string) =>
    get<ProjectReport>(
      `/api/projects/report${path ? `?path=${encodeURIComponent(path)}` : ""}`,
    ),
  refreshReport: (path?: string) =>
    post<ProjectReport>(
      `/api/projects/report/refresh${path ? `?path=${encodeURIComponent(path)}` : ""}`,
    ),
  improve: (id: string) => get<PromptImprovement>(`/api/prompts/${id}/improve`),
  factor: (factor: string, path?: string, limit = 10) =>
    get<FactorEvidence>(
      `/api/projects/factor?factor=${encodeURIComponent(factor)}&limit=${limit}` +
        (path ? `&path=${encodeURIComponent(path)}` : ""),
    ),
  saveAnnotation: (id: string, body: { note?: string; tags?: string[] }) =>
    patch<{ note: string | null; tags: string[] }>(
      `/api/prompts/${id}/annotation`,
      body,
    ),
};

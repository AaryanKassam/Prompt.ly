// Tiny typed client for the Prompt.ly backend.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
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

export const api = {
  sessions: () => get<SessionSummary[]>("/api/sessions"),
  session: (id: string) => get<SessionDetail>(`/api/sessions/${id}`),
  prompt: (id: string) => get<PromptDetail>(`/api/prompts/${id}`),
  saveAnnotation: (id: string, body: { note?: string; tags?: string[] }) =>
    patch<{ note: string | null; tags: string[] }>(
      `/api/prompts/${id}/annotation`,
      body,
    ),
};

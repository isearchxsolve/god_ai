/**
 * Typed client for the OiiOii FastAPI backend.
 *
 * All requests go through the Next.js rewrite proxy (`/api/v1/*` -> backend),
 * so no CORS configuration is needed and generated media at `/media/*` is
 * served from the same origin.
 */

export const API_BASE = '/api/v1';

// ---------------------------------------------------------------------------
// Shared types (mirror backend response shapes)
// ---------------------------------------------------------------------------
export interface ModelItem {
  id: string;
  display_name: string;
  name: string;
  category: 'Video' | 'Image' | 'LLM';
  provider: string;
  url: string;
  capabilities: string[];
  latency_ms_est?: number;
  priority?: number;
  enabled?: boolean;
  speed?: string;
  context_window?: number;
}

export interface ModelsResponse {
  categories: string[];
  counts: { Video: number; Image: number; LLM: number; Total: number };
  video_models: ModelItem[];
  image_models: ModelItem[];
  llm_models: ModelItem[];
}

export interface StyleItem {
  id: string;
  name: string;
  category: string;
  thumbnail: string;
  previewUrl: string;
  promptSuffix: string;
  negativePrompt: string;
  isBuiltIn: boolean;
}

export interface StylesResponse {
  styles: StyleItem[];
  total: number;
  counts: Record<string, number>;
}

export interface ProviderInfo {
  name: string;
  priority: number;
  capabilities: string[];
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  latency_ms: number;
  consecutive_failures: number;
  in_cooldown: boolean;
}

export interface ProvidersHealthResponse {
  status: string;
  active_providers: number;
  providers: ProviderInfo[];
}

export interface ImageGenerationResult {
  data: { url: string; source_url?: string }[];
  provider: string;
  model: string;
  prompt: string;
  local: boolean;
  asset?: unknown;
}

export interface VideoGenerationResult {
  status: string;
  video_url: string;
  duration_seconds: number;
  provider: string;
  model: string;
  prompt: string;
  first_frame?: string | null;
  last_frame?: string | null;
  asset?: unknown;
}

export interface Project {
  id: string;
  user_id: string;
  name: string;
  title?: string;
  idea?: string;
  style_id?: string;
  aspect_ratio?: string;
  status: string;
  final_video_uri?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface AgentRun {
  id: string;
  project_id: string;
  agent: string;
  status: string;
  error?: string;
  created_at?: string;
}

export interface PipelineRunResponse {
  project_id: string;
  status: string;
  stages: { agent: string; status: string }[];
  stream_url?: string;
  final_video_uri?: string | null;
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Registries
// ---------------------------------------------------------------------------
export const getModels = () => request<ModelsResponse>('/models/');
export const getStyles = () => request<StylesResponse>('/styles/');
export const getProvidersHealth = () =>
  request<ProvidersHealthResponse>('/providers/health');

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------
export function generateImage(opts: {
  prompt: string;
  model?: string;
  size?: string;
  style_id?: string;
  project_id?: string;
}): Promise<ImageGenerationResult> {
  return request('/images/generations', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

export function generateVideo(opts: {
  prompt: string;
  model?: string;
  first_frame_url?: string;
  last_frame_url?: string;
  duration_seconds?: number;
  size?: string;
  project_id?: string;
}): Promise<VideoGenerationResult> {
  return request('/videos/generations', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

// ---------------------------------------------------------------------------
// Chat (non-streaming)
// ---------------------------------------------------------------------------
export function chatCompletion(opts: {
  messages: { role: string; content: string }[];
  model?: string;
  temperature?: number;
  max_tokens?: number;
}): Promise<{
  id: string;
  model: string;
  provider: string;
  choices: { message: { role: string; content: string } }[];
}> {
  return request('/chat/completions', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------
export const listProjects = () =>
  request<{ projects: Project[] }>('/projects/');

export function createProject(opts: {
  name?: string;
  title?: string;
  idea?: string;
  style_id?: string;
  aspect_ratio?: string;
}): Promise<Project> {
  return request('/projects/', { method: 'POST', body: JSON.stringify(opts) });
}

export const getProject = (id: string) =>
  request<Project & { frames?: unknown[]; assets?: unknown[]; agent_runs?: AgentRun[] }>(
    `/projects/${id}`
  );

// ---------------------------------------------------------------------------
// Pipeline
// ---------------------------------------------------------------------------
export function runPipeline(opts: {
  project_id: string;
  idea: string;
  style?: string;
  style_id?: string;
  aspect_ratio?: string;
  duration?: number;
  wait?: boolean;
}): Promise<PipelineRunResponse> {
  return request(`/projects/${opts.project_id}/pipeline/run`, {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

export const getPipelineStatus = (projectId: string) =>
  request<{ project_id: string; status: string; agent_runs: AgentRun[] }>(
    `/projects/${projectId}/pipeline/status`
  );

/** URL for the pipeline SSE stream (EventSource cannot set headers). */
export const pipelineStreamUrl = (projectId: string) =>
  `${API_BASE}/projects/${projectId}/pipeline/stream`;

/** URL for the chat SSE stream. */
export const chatStreamUrl = (prompt: string, model?: string) => {
  const params = new URLSearchParams({ prompt });
  if (model) params.set('model', model);
  return `${API_BASE}/chat/stream?${params.toString()}`;
};

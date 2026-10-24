import type {
  AssumptionsPayload,
  Decision,
  EvidenceBundle,
  Frame,
  Incident,
  NetworkDescription,
  Preset,
  RunSummary,
  ScenarioConfig,
  TruthBundle,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // keep the HTTP status text
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export const api = {
  network: () => request<NetworkDescription>('/api/network'),
  scenarios: () =>
    request<{ presets: Preset[]; network_version: string; labels: Record<string, string> }>(
      '/api/scenarios',
    ),
  runs: () => request<{ runs: RunSummary[] }>('/api/runs'),
  run: (runId: string) => request<RunSummary>(`/api/runs/${runId}`),
  startRun: (body: { scenario_id?: string; config?: ScenarioConfig; speed?: number }) =>
    request<RunSummary>('/api/runs', { method: 'POST', body: JSON.stringify(body) }),
  truth: (runId: string) => request<TruthBundle>(`/api/runs/${runId}/truth`),
  incidents: (runId: string) =>
    request<{ run_id: string; incidents: Incident[] }>(`/api/runs/${runId}/alerts`),
  incident: (incidentId: string) => request<Incident>(`/api/incidents/${incidentId}`),
  evidence: (incidentId: string) =>
    request<EvidenceBundle>(`/api/incidents/${incidentId}/evidence`),
  analyze: (incidentId: string, body: { budget?: number | null; max_unserved_m3?: number | null }) =>
    request<Decision>(`/api/incidents/${incidentId}/analyze`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  assumptions: () => request<AssumptionsPayload>('/api/assumptions'),
  updateAssumptions: (values: Record<string, number>) =>
    request<AssumptionsPayload>('/api/assumptions', {
      method: 'PUT',
      body: JSON.stringify({ values }),
    }),
};

export function openStream(runId: string, speed: number): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return new WebSocket(`${protocol}//${window.location.host}/ws/runs/${runId}?speed=${speed}`);
}

export type StreamControl =
  | { action: 'pause' }
  | { action: 'resume' }
  | { action: 'speed'; value: number }
  | { action: 'jump'; value: number }
  | { action: 'frame' };

export function parseFrame(raw: string): Frame {
  return JSON.parse(raw) as Frame;
}

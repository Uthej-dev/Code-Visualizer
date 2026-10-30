import type { Sample, TraceResponse } from '../types/trace';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      'Could not reach the execution server. Make sure the backend is running (see README: "uvicorn app.main:app --port 8000").',
    );
  }
  if (!response.ok) {
    let detail = `The server responded with status ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = 'The request was rejected: ' + body.detail.map((d: { msg: string }) => d.msg).join('; ');
    } catch {
      /* keep generic message */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export function fetchTrace(code: string, signal?: AbortSignal): Promise<TraceResponse> {
  return request<TraceResponse>('/api/trace', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
    signal,
  });
}

export function fetchSamples(): Promise<Sample[]> {
  return request<Sample[]>('/api/samples');
}

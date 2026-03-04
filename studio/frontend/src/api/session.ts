import type {
  SessionEventsResponse,
  SessionInterruptResponse,
  SessionMessageResponse,
  SessionStartResponse,
  SessionStopResponse,
} from "./types";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function startSession(payload: {
  profile_name: string;
  dataset_path?: string;
  export_path?: string;
  verbose?: boolean;
}): Promise<SessionStartResponse> {
  const res = await fetch("/api/session/start", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson<SessionStartResponse>(res);
}

export async function sendSessionMessage(payload: {
  session_id: string;
  message: string;
  client_message_id?: string;
}): Promise<SessionMessageResponse> {
  const res = await fetch("/api/session/message", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson<SessionMessageResponse>(res);
}

export async function fetchSessionEvents(params: {
  session_id: string;
  after?: number;
  limit?: number;
}): Promise<SessionEventsResponse> {
  const search = new URLSearchParams({
    session_id: params.session_id,
    after: String(params.after ?? 0),
    limit: String(params.limit ?? 200),
  });
  const res = await fetch(`/api/session/events?${search.toString()}`);
  return parseJson<SessionEventsResponse>(res);
}

export async function stopSession(payload: { session_id: string }): Promise<SessionStopResponse> {
  const res = await fetch("/api/session/stop", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson<SessionStopResponse>(res);
}

export async function interruptSession(payload: { session_id: string }): Promise<SessionInterruptResponse> {
  const res = await fetch("/api/session/interrupt", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson<SessionInterruptResponse>(res);
}

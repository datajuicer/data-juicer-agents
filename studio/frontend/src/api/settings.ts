import type {
  ConnectionTestResponse,
  SettingsProfileResponse,
  SettingsUpdateRequest,
} from "./types";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchSettingsProfile(profileName = "default"): Promise<SettingsProfileResponse> {
  const res = await fetch(`/api/settings/profile?profile_name=${encodeURIComponent(profileName)}`);
  return parseJson<SettingsProfileResponse>(res);
}

export async function updateSettingsProfile(payload: SettingsUpdateRequest): Promise<SettingsProfileResponse> {
  const res = await fetch("/api/settings/profile", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson<SettingsProfileResponse>(res);
}

export async function testSettingsConnection(payload: {
  profile_name: string;
  override?: {
    dashscope_api_key?: string;
    session_model?: string;
    planner_model?: string;
    validator_model?: string;
    thinking?: boolean;
    base_url?: string;
  };
}): Promise<ConnectionTestResponse> {
  const res = await fetch("/api/settings/test-connection", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseJson<ConnectionTestResponse>(res);
}

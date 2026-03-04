export interface SettingsProfilePublic {
  has_api_key: boolean;
  dashscope_api_key_masked: string | null;
  session_model: string;
  planner_model: string;
  validator_model: string;
  thinking: boolean;
  base_url: string;
}

export interface SettingsProfileResponse {
  ok: boolean;
  profile_name: string;
  profile: SettingsProfilePublic;
  config_path: string;
}

export interface SettingsProfilePatch {
  dashscope_api_key?: string;
  session_model?: string;
  planner_model?: string;
  validator_model?: string;
  thinking?: boolean;
  base_url?: string;
}

export interface SettingsUpdateRequest extends SettingsProfilePatch {
  profile_name: string;
}

export interface ConnectionTestResponse {
  ok: boolean;
  endpoint: string;
  message: string;
  status_code: number | null;
  models: string[];
}

export interface SessionEvent {
  seq: number;
  session_id: string;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface SessionStartResponse {
  ok: boolean;
  session_id: string;
  profile_name: string;
  created_at: string;
  context: Record<string, unknown>;
  events: SessionEvent[];
}

export interface SessionMessageResponse {
  ok: boolean;
  session_id: string;
  reply_text: string;
  stop: boolean;
  interrupted: boolean;
  context: Record<string, unknown>;
  events: SessionEvent[];
  next_seq: number;
}

export interface SessionEventsResponse {
  ok: boolean;
  session_id: string;
  events: SessionEvent[];
  next_seq: number;
}

export interface SessionStopResponse {
  ok: boolean;
  session_id: string;
  stopped: boolean;
}

export interface SessionInterruptResponse {
  ok: boolean;
  session_id: string;
  accepted: boolean;
}

export interface PlanLoadResponse {
  ok: boolean;
  path: string;
  plan: Record<string, unknown>;
  warnings: string[];
}

export interface PlanSaveResponse {
  ok: boolean;
  path: string;
  plan: Record<string, unknown>;
  warnings: string[];
}

export interface DataSampleBlock {
  path: string;
  exists: boolean;
  keys: string[];
  records: Record<string, unknown>[];
  sample_count: number;
  truncated: boolean;
  modality: string;
}

export interface DataPreviewResponse {
  ok: boolean;
  sample: DataSampleBlock;
  warnings: string[];
}

export interface DataCompareByRunResponse {
  ok: boolean;
  run_id: string;
  plan_id: string | null;
  dataset_path: string | null;
  export_path: string | null;
  input: DataSampleBlock | null;
  output: DataSampleBlock | null;
  warnings: string[];
}

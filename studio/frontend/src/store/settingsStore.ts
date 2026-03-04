import { create } from "zustand";

interface SettingsDraft {
  profileName: string;
  apiKeyInput: string;
  sessionModel: string;
  plannerModel: string;
  validatorModel: string;
  baseUrl: string;
  thinking: boolean;
  clearApiKey: boolean;
}

interface SettingsStoreState {
  draft: SettingsDraft;
  apiKeyMasked: string | null;
  hasApiKey: boolean;
  configPath: string;
  setField: <K extends keyof SettingsDraft>(key: K, value: SettingsDraft[K]) => void;
  hydrateFromProfile: (payload: {
    profileName: string;
    apiKeyMasked: string | null;
    hasApiKey: boolean;
    sessionModel: string;
    plannerModel: string;
    validatorModel: string;
    baseUrl: string;
    thinking: boolean;
    configPath: string;
  }) => void;
}

const DEFAULT_DRAFT: SettingsDraft = {
  profileName: "default",
  apiKeyInput: "",
  sessionModel: "qwen3-max-2026-01-23",
  plannerModel: "qwen3-max-2026-01-23",
  validatorModel: "qwen3-max-2026-01-23",
  baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  thinking: true,
  clearApiKey: false,
};

export const useSettingsStore = create<SettingsStoreState>((set) => ({
  draft: { ...DEFAULT_DRAFT },
  apiKeyMasked: null,
  hasApiKey: false,
  configPath: "",
  setField: (key, value) =>
    set((state) => ({
      draft: {
        ...state.draft,
        [key]: value,
      },
    })),
  hydrateFromProfile: (payload) =>
    set((state) => ({
      draft: {
        ...state.draft,
        profileName: payload.profileName,
        apiKeyInput: "",
        sessionModel: payload.sessionModel,
        plannerModel: payload.plannerModel,
        validatorModel: payload.validatorModel,
        baseUrl: payload.baseUrl,
        thinking: payload.thinking,
        clearApiKey: false,
      },
      apiKeyMasked: payload.apiKeyMasked,
      hasApiKey: payload.hasApiKey,
      configPath: payload.configPath,
    })),
}));

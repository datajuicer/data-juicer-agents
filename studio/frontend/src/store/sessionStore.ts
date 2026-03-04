import { create } from "zustand";

export interface SessionContextState {
  datasetPath: string;
  exportPath: string;
  planPath: string;
  runId: string;
  customOperatorPaths: string[];
}

interface SessionStoreState {
  sessionId: string;
  context: SessionContextState;
  setSession: (sessionId: string) => void;
  setContextFromPayload: (payload: Record<string, unknown>) => void;
  clearSession: () => void;
}

const DEFAULT_CONTEXT: SessionContextState = {
  datasetPath: "",
  exportPath: "",
  planPath: "",
  runId: "",
  customOperatorPaths: [],
};

function toStringValue(value: unknown): string {
  return String(value ?? "").trim();
}

function toStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item ?? "").trim())
      .filter((item) => item.length > 0);
  }
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }
  return [];
}

export const useSessionStore = create<SessionStoreState>((set) => ({
  sessionId: "",
  context: { ...DEFAULT_CONTEXT },
  setSession: (sessionId) =>
    set(() => ({
      sessionId: toStringValue(sessionId),
    })),
  setContextFromPayload: (payload) =>
    set((state) => ({
      context: {
        datasetPath: toStringValue(payload.dataset_path) || state.context.datasetPath,
        exportPath: toStringValue(payload.export_path) || state.context.exportPath,
        planPath: toStringValue(payload.plan_path) || state.context.planPath,
        runId: toStringValue(payload.run_id) || state.context.runId,
        customOperatorPaths:
          toStringArray(payload.custom_operator_paths).length > 0
            ? toStringArray(payload.custom_operator_paths)
            : state.context.customOperatorPaths,
      },
    })),
  clearSession: () =>
    set(() => ({
      sessionId: "",
      context: { ...DEFAULT_CONTEXT },
    })),
}));

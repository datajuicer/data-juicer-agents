import type {
  DataCompareByRunResponse,
  DataPreviewResponse,
  PlanLoadResponse,
  PlanSaveResponse,
} from "./types";

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadPlan(path: string): Promise<PlanLoadResponse> {
  const search = new URLSearchParams({ path });
  const res = await fetch(`/api/plan?${search.toString()}`);
  return parseJson<PlanLoadResponse>(res);
}

export async function savePlan(path: string, plan: Record<string, unknown>): Promise<PlanSaveResponse> {
  const res = await fetch("/api/plan", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path, plan }),
  });
  return parseJson<PlanSaveResponse>(res);
}

export async function previewData(path: string, limit = 20, offset = 0): Promise<DataPreviewResponse> {
  const search = new URLSearchParams({
    path,
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(`/api/data/preview?${search.toString()}`);
  return parseJson<DataPreviewResponse>(res);
}

export async function compareDataByRun(
  runId: string,
  limit = 20,
  offset = 0,
): Promise<DataCompareByRunResponse> {
  const search = new URLSearchParams({
    run_id: runId,
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(`/api/data/compare-by-run?${search.toString()}`);
  return parseJson<DataCompareByRunResponse>(res);
}

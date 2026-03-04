import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { loadPlan, savePlan } from "../api/workspace";
import { useSessionStore } from "../store/sessionStore";
import { useI18n } from "../i18n";

interface OperatorEditor {
  id: string;
  name: string;
  paramsText: string;
}

function toStringValue(value: unknown): string {
  return String(value ?? "").trim();
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter((item) => item.length > 0);
}

function toJsonPretty(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return "{}";
  }
}

function buildOperatorEditors(raw: unknown): OperatorEditor[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const rows: OperatorEditor[] = [];
  raw.forEach((item, idx) => {
    if (!item || typeof item !== "object") {
      return;
    }
    const op = item as Record<string, unknown>;
    rows.push({
      id: `op_${Date.now()}_${idx}_${Math.random().toString(36).slice(2, 8)}`,
      name: toStringValue(op.name),
      paramsText: toJsonPretty(op.params),
    });
  });
  return rows;
}

function parseJsonObject(text: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  if (!text.trim()) {
    return { ok: true, value: {} };
  }
  try {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: "must be a JSON object" };
    }
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

export default function RecipePanel() {
  const { t } = useI18n();
  const sessionId = useSessionStore((state) => state.sessionId);
  const context = useSessionStore((state) => state.context);

  const [planPath, setPlanPath] = useState("");
  const [loadedPath, setLoadedPath] = useState("");
  const [rawPlan, setRawPlan] = useState<Record<string, unknown> | null>(null);

  const [workflow, setWorkflow] = useState("custom");
  const [modality, setModality] = useState("unknown");
  const [datasetPath, setDatasetPath] = useState("");
  const [exportPath, setExportPath] = useState("");
  const [textKeysInput, setTextKeysInput] = useState("");
  const [imageKeyInput, setImageKeyInput] = useState("");
  const [riskNotesInput, setRiskNotesInput] = useState("");
  const [customPathsInput, setCustomPathsInput] = useState("");
  const [estimationInput, setEstimationInput] = useState("{}");
  const [operators, setOperators] = useState<OperatorEditor[]>([]);

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  const normalizeParserError = (raw: string) =>
    raw === "must be a JSON object" ? t("recipe.error.jsonObjectRequired") : raw;

  useEffect(() => {
    if (!context.planPath) {
      return;
    }
    if (!planPath || (!isDirty && planPath === loadedPath)) {
      setPlanPath(context.planPath);
    }
  }, [context.planPath, isDirty, loadedPath, planPath]);

  useEffect(() => {
    const incomingPath = String(context.planPath || "").trim();
    if (!incomingPath || isDirty) {
      return;
    }
    if (incomingPath === loadedPath) {
      return;
    }
    setPlanPath(incomingPath);
    loadMutation.mutate(incomingPath);
  }, [context.planPath, isDirty, loadedPath]);

  const loadMutation = useMutation({
    mutationFn: loadPlan,
    onSuccess: (payload) => {
      const plan = payload.plan ?? {};
      setRawPlan(plan);
      setLoadedPath(payload.path);
      setWarnings(payload.warnings ?? []);

      setWorkflow(toStringValue(plan.workflow) || "custom");
      setModality(toStringValue(plan.modality) || "unknown");
      setDatasetPath(toStringValue(plan.dataset_path));
      setExportPath(toStringValue(plan.export_path));
      setTextKeysInput(toStringArray(plan.text_keys).join(", "));
      setImageKeyInput(toStringValue(plan.image_key));
      setRiskNotesInput(toStringArray(plan.risk_notes).join("\n"));
      setCustomPathsInput(toStringArray(plan.custom_operator_paths).join("\n"));
      setEstimationInput(toJsonPretty(plan.estimation));
      setOperators(buildOperatorEditors(plan.operators));
      setError("");
      setSuccess(t("recipe.status.planLoaded"));
      setIsDirty(false);
    },
    onError: (err) => {
      setError(t("recipe.error.loadFailed", { error: String(err) }));
      setSuccess("");
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (payload: { path: string; plan: Record<string, unknown> }) =>
      savePlan(payload.path, payload.plan),
    onSuccess: (payload) => {
      setRawPlan(payload.plan);
      setLoadedPath(payload.path);
      setWarnings(payload.warnings ?? []);
      setError("");
      setSuccess(t("recipe.status.planSaved"));
      setIsDirty(false);
    },
    onError: (err) => {
      setError(t("recipe.error.saveFailed", { error: String(err) }));
      setSuccess("");
    },
  });

  const canSave = Boolean(rawPlan) && Boolean(planPath.trim()) && !saveMutation.isPending;
  const operatorCount = operators.length;

  const planSummary = useMemo(() => {
    const planId = toStringValue(rawPlan?.plan_id);
    const revision = toStringValue(rawPlan?.revision);
    return {
      planId: planId || "-",
      revision: revision || "-",
    };
  }, [rawPlan]);

  const onLoad = async () => {
    if (!planPath.trim()) {
      setError(t("recipe.error.providePlanPath"));
      return;
    }
    await loadMutation.mutateAsync(planPath.trim());
  };

  const onAddOperator = () => {
    setOperators((prev) => [
      ...prev,
      {
        id: `op_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        name: "",
        paramsText: "{}",
      },
    ]);
    setIsDirty(true);
  };

  const onMoveOperator = (idx: number, offset: number) => {
    setOperators((prev) => {
      const target = idx + offset;
      if (target < 0 || target >= prev.length) {
        return prev;
      }
      const next = [...prev];
      const temp = next[idx];
      next[idx] = next[target];
      next[target] = temp;
      return next;
    });
    setIsDirty(true);
  };

  const onDeleteOperator = (idx: number) => {
    setOperators((prev) => prev.filter((_, index) => index !== idx));
    setIsDirty(true);
  };

  const onSave = async () => {
    if (!rawPlan) {
      setError(t("recipe.error.loadFirst"));
      return;
    }
    if (!planPath.trim()) {
      setError(t("recipe.error.planPathRequired"));
      return;
    }

    const parsedOperators = [];
    for (let idx = 0; idx < operators.length; idx += 1) {
      const item = operators[idx];
      const name = item.name.trim();
      if (!name) {
        setError(t("recipe.error.operatorNameRequired", { index: idx + 1 }));
        return;
      }
      const parsed = parseJsonObject(item.paramsText);
      if (!parsed.ok) {
        setError(t("recipe.error.operatorParamsInvalid", { index: idx + 1, error: normalizeParserError(parsed.error) }));
        return;
      }
      parsedOperators.push({
        name,
        params: parsed.value,
      });
    }
    if (parsedOperators.length === 0) {
      setError(t("recipe.error.operatorRequired"));
      return;
    }

    const estimationParsed = parseJsonObject(estimationInput);
    if (!estimationParsed.ok) {
      setError(t("recipe.error.estimationInvalid", { error: normalizeParserError(estimationParsed.error) }));
      return;
    }

    const nextPlan: Record<string, unknown> = {
      ...rawPlan,
      workflow: workflow.trim() || "custom",
      modality: modality.trim() || "unknown",
      dataset_path: datasetPath.trim(),
      export_path: exportPath.trim(),
      text_keys: textKeysInput
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
      image_key: imageKeyInput.trim() || null,
      operators: parsedOperators,
      risk_notes: riskNotesInput
        .split("\n")
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
      custom_operator_paths: customPathsInput
        .split("\n")
        .map((item) => item.trim())
        .filter((item) => item.length > 0),
      estimation: estimationParsed.value,
    };

    await saveMutation.mutateAsync({
      path: planPath.trim(),
      plan: nextPlan,
    });
  };

  return (
    <section className="panel-card recipe-panel" aria-label={t("recipe.title")}>
      <header className="panel-head">
        <h2>{t("recipe.title")}</h2>
        <p>{t("recipe.description")}</p>
        <p className="muted">
          {t("recipe.context", {
            session: sessionId || "-",
            planPath: context.planPath || "-",
            runId: context.runId || "-",
          })}
        </p>
      </header>

      <div className="panel-scroll-body">
        <div className="recipe-path-row">
          <input
            value={planPath}
            onChange={(e) => {
              setPlanPath(e.target.value);
              setIsDirty(true);
            }}
            placeholder={t("recipe.input.planPath")}
          />
          <button type="button" onClick={onLoad} disabled={loadMutation.isPending}>
            {loadMutation.isPending ? t("recipe.btn.loading") : t("recipe.btn.loadPlan")}
          </button>
        </div>

        <div className="recipe-meta-grid">
          <label>
            {t("recipe.label.workflow")}
            <select
              value={workflow}
              onChange={(e) => {
                setWorkflow(e.target.value);
                setIsDirty(true);
              }}
            >
              <option value="custom">{t("recipe.workflow.custom")}</option>
              <option value="rag_cleaning">{t("recipe.workflow.rag")}</option>
              <option value="multimodal_dedup">{t("recipe.workflow.multimodal")}</option>
            </select>
          </label>
          <label>
            {t("recipe.label.modality")}
            <select
              value={modality}
              onChange={(e) => {
                setModality(e.target.value);
                setIsDirty(true);
              }}
            >
              <option value="unknown">{t("recipe.modality.unknown")}</option>
              <option value="text">{t("recipe.modality.text")}</option>
              <option value="image">{t("recipe.modality.image")}</option>
              <option value="multimodal">{t("recipe.modality.multimodal")}</option>
            </select>
          </label>
          <label>
            {t("recipe.label.planId")}
            <input value={planSummary.planId} readOnly />
          </label>
          <label>
            {t("recipe.label.revision")}
            <input value={planSummary.revision} readOnly />
          </label>
        </div>

        <div className="recipe-fields-grid">
          <label>
            {t("recipe.label.datasetPath")}
            <input
              value={datasetPath}
              onChange={(e) => {
                setDatasetPath(e.target.value);
                setIsDirty(true);
              }}
            />
          </label>
          <label>
            {t("recipe.label.exportPath")}
            <input
              value={exportPath}
              onChange={(e) => {
                setExportPath(e.target.value);
                setIsDirty(true);
              }}
            />
          </label>
          <label>
            {t("recipe.label.textKeys")}
            <input
              value={textKeysInput}
              onChange={(e) => {
                setTextKeysInput(e.target.value);
                setIsDirty(true);
              }}
            />
          </label>
          <label>
            {t("recipe.label.imageKey")}
            <input
              value={imageKeyInput}
              onChange={(e) => {
                setImageKeyInput(e.target.value);
                setIsDirty(true);
              }}
            />
          </label>
        </div>

        <div className="recipe-textareas">
          <label>
            {t("recipe.label.riskNotes")}
            <textarea
              value={riskNotesInput}
              onChange={(e) => {
                setRiskNotesInput(e.target.value);
                setIsDirty(true);
              }}
              rows={3}
            />
          </label>
          <label>
            {t("recipe.label.customOperatorPaths")}
            <textarea
              value={customPathsInput}
              onChange={(e) => {
                setCustomPathsInput(e.target.value);
                setIsDirty(true);
              }}
              rows={3}
            />
          </label>
          <label>
            {t("recipe.label.estimation")}
            <textarea
              value={estimationInput}
              onChange={(e) => {
                setEstimationInput(e.target.value);
                setIsDirty(true);
              }}
              rows={4}
            />
          </label>
        </div>

        <div className="recipe-operator-head">
          <h3>{t("recipe.operators", { count: operatorCount })}</h3>
          <button type="button" onClick={onAddOperator}>
            {t("recipe.btn.addOperator")}
          </button>
        </div>

        <div className="operator-list">
          {operators.length === 0 ? <p className="muted">{t("recipe.empty.noOperators")}</p> : null}
          {operators.map((item, idx) => (
            <article key={item.id} className="operator-card">
              <div className="operator-card-head">
                <span>#{idx + 1}</span>
                <div className="operator-actions">
                  <button type="button" onClick={() => onMoveOperator(idx, -1)} disabled={idx === 0}>
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => onMoveOperator(idx, 1)}
                    disabled={idx === operators.length - 1}
                  >
                    ↓
                  </button>
                  <button type="button" onClick={() => onDeleteOperator(idx)}>
                    {t("recipe.btn.delete")}
                  </button>
                </div>
              </div>
              <label>
                {t("recipe.label.operatorName")}
                <input
                  value={item.name}
                  onChange={(e) => {
                    const next = [...operators];
                    next[idx] = { ...item, name: e.target.value };
                    setOperators(next);
                    setIsDirty(true);
                  }}
                />
              </label>
              <label>
                {t("recipe.label.operatorParams")}
                <textarea
                  value={item.paramsText}
                  onChange={(e) => {
                    const next = [...operators];
                    next[idx] = { ...item, paramsText: e.target.value };
                    setOperators(next);
                    setIsDirty(true);
                  }}
                  rows={5}
                />
              </label>
            </article>
          ))}
        </div>

        <div className="panel-actions">
          <button type="button" onClick={onSave} disabled={!canSave}>
            {saveMutation.isPending ? t("recipe.btn.saving") : t("recipe.btn.savePlan")}
          </button>
          <button
            type="button"
            onClick={onLoad}
            disabled={!loadedPath || loadMutation.isPending}
            className="secondary-btn"
          >
            {t("recipe.btn.reload")}
          </button>
          <span className="muted">{t("recipe.loadedPath", { path: loadedPath || "-" })}</span>
        </div>

        {warnings.length > 0 ? (
          <ul className="panel-warning-list">
            {warnings.map((item, idx) => (
              <li key={`${item}_${idx}`}>{item}</li>
            ))}
          </ul>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
        {success ? (
          <p className="ok">
            {success}
            {isDirty ? t("recipe.status.unsaved") : ""}
          </p>
        ) : null}
      </div>
    </section>
  );
}

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { compareDataByRun, previewData } from "../api/workspace";
import type { DataSampleBlock } from "../api/types";
import { useSessionStore } from "../store/sessionStore";
import { useI18n } from "../i18n";

function toDisplayText(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value ?? "");
  }
}

function SampleCard(props: {
  title: string;
  sample: DataSampleBlock | null;
  t: (key: string, params?: Record<string, string | number | boolean | null | undefined>) => string;
}) {
  const sample = props.sample;
  const { t } = props;
  if (!sample) {
    return (
      <section className="data-sample-card">
        <h4>{props.title}</h4>
        <p className="muted">{t("data.sample.none")}</p>
      </section>
    );
  }

  return (
      <section className="data-sample-card">
      <h4>{props.title}</h4>
      <p className="muted">
        {t("data.sample.meta1", {
          path: sample.path,
          exists: String(sample.exists),
          modality: sample.modality,
        })}
      </p>
      <p className="muted">
        {t("data.sample.meta2", {
          count: sample.sample_count,
          suffix: sample.truncated ? t("data.sample.truncated") : "",
        })}
      </p>
      <p className="muted">{t("data.sample.keys", { keys: sample.keys.join(", ") || "-" })}</p>
      <div className="data-record-list">
        {sample.records.map((row, idx) => (
          <article key={`${props.title}_${idx}`} className="data-record-item">
            <p className="muted">#{idx + 1}</p>
            <pre>{JSON.stringify(row, null, 2)}</pre>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function DataPanel() {
  const { t } = useI18n();
  const sessionId = useSessionStore((state) => state.sessionId);
  const context = useSessionStore((state) => state.context);

  const [datasetPath, setDatasetPath] = useState("");
  const [exportPath, setExportPath] = useState("");
  const [runId, setRunId] = useState("");
  const [limit, setLimit] = useState(20);

  const [inputSample, setInputSample] = useState<DataSampleBlock | null>(null);
  const [outputSample, setOutputSample] = useState<DataSampleBlock | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (context.datasetPath && !datasetPath) {
      setDatasetPath(context.datasetPath);
    }
    if (context.exportPath && !exportPath) {
      setExportPath(context.exportPath);
    }
    if (context.runId && !runId) {
      setRunId(context.runId);
    }
  }, [context.datasetPath, context.exportPath, context.runId, datasetPath, exportPath, runId]);

  const previewMutation = useMutation({
    mutationFn: async (payload: { path: string; kind: "input" | "output" }) => {
      const data = await previewData(payload.path, limit, 0);
      return {
        kind: payload.kind,
        data,
      };
    },
    onSuccess: (payload) => {
      if (payload.kind === "input") {
        setInputSample(payload.data.sample);
      } else {
        setOutputSample(payload.data.sample);
      }
      setWarnings((prev) => [...prev, ...(payload.data.warnings ?? [])]);
      setError("");
    },
    onError: (err) => {
      setError(t("data.error.previewFailed", { error: String(err) }));
    },
  });

  const compareMutation = useMutation({
    mutationFn: async (id: string) => compareDataByRun(id, limit, 0),
    onSuccess: (payload) => {
      setRunId(payload.run_id || runId);
      if (payload.dataset_path) {
        setDatasetPath(payload.dataset_path);
      }
      if (payload.export_path) {
        setExportPath(payload.export_path);
      }
      setInputSample(payload.input ?? null);
      setOutputSample(payload.output ?? null);
      setWarnings(payload.warnings ?? []);
      setError("");
    },
    onError: (err) => {
      setError(t("data.error.compareFailed", { error: String(err) }));
    },
  });

  const onPreviewInput = async () => {
    if (!datasetPath.trim()) {
      setError(t("data.error.datasetPathRequired"));
      return;
    }
    await previewMutation.mutateAsync({
      path: datasetPath.trim(),
      kind: "input",
    });
  };

  const onPreviewOutput = async () => {
    if (!exportPath.trim()) {
      setError(t("data.error.exportPathRequired"));
      return;
    }
    await previewMutation.mutateAsync({
      path: exportPath.trim(),
      kind: "output",
    });
  };

  const onCompareByRun = async () => {
    if (!runId.trim()) {
      setError(t("data.error.runIdRequired"));
      return;
    }
    await compareMutation.mutateAsync(runId.trim());
  };

  return (
    <section className="panel-card data-panel" aria-label={t("data.title")}>
      <header className="panel-head">
        <h2>{t("data.title")}</h2>
        <p>{t("data.description")}</p>
        <p className="muted">
          {t("data.context", {
            session: sessionId || "-",
            runId: context.runId || "-",
            planPath: context.planPath || "-",
          })}
        </p>
      </header>

      <div className="panel-scroll-body">
        <div className="data-controls-grid">
          <label>
            {t("data.label.datasetPath")}
            <input
              value={datasetPath}
              onChange={(e) => setDatasetPath(e.target.value)}
              placeholder={t("data.input.datasetPath")}
            />
          </label>
          <label>
            {t("data.label.exportPath")}
            <input
              value={exportPath}
              onChange={(e) => setExportPath(e.target.value)}
              placeholder={t("data.input.exportPath")}
            />
          </label>
          <label>
            {t("data.label.runId")}
            <input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder={t("data.input.runId")} />
          </label>
          <label>
            {t("data.label.sampleLimit")}
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(Math.max(1, Math.min(200, Number(e.target.value || 20))))}
            />
          </label>
        </div>

        <div className="panel-actions">
          <button type="button" onClick={onPreviewInput} disabled={previewMutation.isPending}>
            {t("data.btn.previewInput")}
          </button>
          <button type="button" onClick={onPreviewOutput} disabled={previewMutation.isPending}>
            {t("data.btn.previewOutput")}
          </button>
          <button type="button" onClick={onCompareByRun} disabled={compareMutation.isPending}>
            {compareMutation.isPending ? t("data.btn.comparing") : t("data.btn.compareByRun")}
          </button>
        </div>

        <div className="data-sample-grid">
          <SampleCard title={t("data.sample.input")} sample={inputSample} t={t} />
          <SampleCard title={t("data.sample.output")} sample={outputSample} t={t} />
        </div>

        {warnings.length > 0 ? (
          <ul className="panel-warning-list">
            {warnings.map((item, idx) => (
              <li key={`${item}_${idx}`}>{toDisplayText(item)}</li>
            ))}
          </ul>
        ) : null}

        {error ? <p className="error">{error}</p> : null}
      </div>
    </section>
  );
}

import { useEffect, useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { fetchSettingsProfile, testSettingsConnection, updateSettingsProfile } from "../api/settings";
import { useSettingsStore } from "../store/settingsStore";
import { useI18n } from "../i18n";

function sanitizeUrl(value: string): string {
  return value.trim().replace(/\/$/, "");
}

export default function SettingsPanel() {
  const { t } = useI18n();
  const { draft, setField, hydrateFromProfile, apiKeyMasked, hasApiKey, configPath } = useSettingsStore();

  const profileQuery = useQuery({
    queryKey: ["settings-profile", draft.profileName],
    queryFn: () => fetchSettingsProfile(draft.profileName),
  });

  useEffect(() => {
    const payload = profileQuery.data;
    if (!payload) {
      return;
    }
    hydrateFromProfile({
      profileName: payload.profile_name,
      apiKeyMasked: payload.profile.dashscope_api_key_masked,
      hasApiKey: payload.profile.has_api_key,
      sessionModel: payload.profile.session_model,
      plannerModel: payload.profile.planner_model,
      validatorModel: payload.profile.validator_model,
      baseUrl: payload.profile.base_url,
      thinking: payload.profile.thinking,
      configPath: payload.config_path,
    });
  }, [profileQuery.data, hydrateFromProfile]);

  const saveMutation = useMutation({
    mutationFn: updateSettingsProfile,
    onSuccess: (payload) => {
      hydrateFromProfile({
        profileName: payload.profile_name,
        apiKeyMasked: payload.profile.dashscope_api_key_masked,
        hasApiKey: payload.profile.has_api_key,
        sessionModel: payload.profile.session_model,
        plannerModel: payload.profile.planner_model,
        validatorModel: payload.profile.validator_model,
        baseUrl: payload.profile.base_url,
        thinking: payload.profile.thinking,
        configPath: payload.config_path,
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: testSettingsConnection,
  });

  const testStatusText = useMemo(() => {
    if (!testMutation.data) {
      return "";
    }
    const result = testMutation.data;
    const prefix = result.ok ? t("settings.status.connected") : t("settings.status.failed");
    const models = result.models.length > 0 ? ` | ${t("settings.status.models")}: ${result.models.join(", ")}` : "";
    return `${prefix} | ${result.message}${models}`;
  }, [testMutation.data, t]);

  const onSave = async () => {
    const payload: Record<string, unknown> = {
      profile_name: draft.profileName,
      session_model: draft.sessionModel.trim(),
      planner_model: draft.plannerModel.trim(),
      validator_model: draft.validatorModel.trim(),
      base_url: sanitizeUrl(draft.baseUrl),
      thinking: draft.thinking,
    };

    if (draft.clearApiKey) {
      payload.dashscope_api_key = "";
    } else if (draft.apiKeyInput.trim()) {
      payload.dashscope_api_key = draft.apiKeyInput.trim();
    }

    await saveMutation.mutateAsync(payload as never);
  };

  const onTest = async () => {
    const override: Record<string, unknown> = {
      session_model: draft.sessionModel.trim(),
      planner_model: draft.plannerModel.trim(),
      validator_model: draft.validatorModel.trim(),
      base_url: sanitizeUrl(draft.baseUrl),
      thinking: draft.thinking,
    };

    if (draft.clearApiKey) {
      override.dashscope_api_key = "";
    } else if (draft.apiKeyInput.trim()) {
      override.dashscope_api_key = draft.apiKeyInput.trim();
    }

    await testMutation.mutateAsync({
      profile_name: draft.profileName,
      override,
    });
  };

  return (
    <section className="panel-card settings-panel">
      <header className="panel-head">
        <h2>{t("settings.title")}</h2>
        <p>{t("settings.description")}</p>
      </header>

      {profileQuery.isError ? <p className="error">{t("settings.error.loadProfile")}</p> : null}
      {profileQuery.isLoading ? <p className="muted">{t("settings.loadingProfile")}</p> : null}

      <div className="form-grid">
        <label>
          {t("settings.label.profile")}
          <input
            value={draft.profileName}
            onChange={(e) => setField("profileName", e.target.value)}
            placeholder={t("settings.placeholder.default")}
          />
        </label>

        <label>
          {t("settings.label.apiKey")}
          <input
            value={draft.apiKeyInput}
            onChange={(e) => setField("apiKeyInput", e.target.value)}
            placeholder={hasApiKey ? apiKeyMasked ?? t("settings.placeholder.stored") : "sk-..."}
            type="password"
          />
        </label>

        <label className="toggle-row">
          <input
            checked={draft.clearApiKey}
            onChange={(e) => setField("clearApiKey", e.target.checked)}
            type="checkbox"
          />
          {t("settings.label.clearApiKey")}
        </label>

        <label>
          {t("settings.label.sessionModel")}
          <input
            value={draft.sessionModel}
            onChange={(e) => setField("sessionModel", e.target.value)}
            placeholder="qwen3-max-2026-01-23"
          />
        </label>

        <label>
          {t("settings.label.plannerModel")}
          <input
            value={draft.plannerModel}
            onChange={(e) => setField("plannerModel", e.target.value)}
            placeholder="qwen3-max-2026-01-23"
          />
        </label>

        <label>
          {t("settings.label.validatorModel")}
          <input
            value={draft.validatorModel}
            onChange={(e) => setField("validatorModel", e.target.value)}
            placeholder="qwen3-max-2026-01-23"
          />
        </label>

        <label>
          {t("settings.label.baseUrl")}
          <input
            value={draft.baseUrl}
            onChange={(e) => setField("baseUrl", e.target.value)}
            placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
          />
        </label>

        <label className="toggle-row">
          <input
            checked={draft.thinking}
            onChange={(e) => setField("thinking", e.target.checked)}
            type="checkbox"
          />
          {t("settings.label.enableThinking")}
        </label>
      </div>

      <div className="action-row">
        <button onClick={onTest} disabled={testMutation.isPending || saveMutation.isPending}>
          {testMutation.isPending ? t("settings.btn.testing") : t("settings.btn.testConnection")}
        </button>
        <button onClick={onSave} disabled={saveMutation.isPending || testMutation.isPending}>
          {saveMutation.isPending ? t("settings.btn.saving") : t("settings.btn.save")}
        </button>
      </div>

      {testStatusText ? <p className={testMutation.data?.ok ? "ok" : "error"}>{testStatusText}</p> : null}
      {saveMutation.isError ? <p className="error">{t("settings.error.saveFailed")}</p> : null}
      {saveMutation.isSuccess ? (
        <p className="ok">{t("settings.status.savedTo", { path: configPath || "./.djx/config.json" })}</p>
      ) : null}
    </section>
  );
}

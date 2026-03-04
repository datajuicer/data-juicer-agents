import { useMemo, useState } from "react";

import ChatPanel from "./components/ChatPanel";
import DataPanel from "./components/DataPanel";
import RecipePanel from "./components/RecipePanel";
import SettingsPanel from "./components/SettingsPanel";
import { useI18n, type UiLanguage } from "./i18n";

type TabKey = "chat" | "recipe" | "data" | "settings";

const TAB_ORDER: Array<{ key: TabKey; labelKey: string }> = [
  { key: "chat", labelKey: "app.tab.chat" },
  { key: "recipe", labelKey: "app.tab.recipe" },
  { key: "data", labelKey: "app.tab.data" },
  { key: "settings", labelKey: "app.tab.settings" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("chat");
  const { lang, setLang, t } = useI18n();

  const activePanel = useMemo(() => {
    if (activeTab === "recipe") {
      return <RecipePanel />;
    }
    if (activeTab === "data") {
      return <DataPanel />;
    }
    if (activeTab === "settings") {
      return <SettingsPanel />;
    }
    return <ChatPanel />;
  }, [activeTab]);

  return (
    <div className="tabs-app-shell">
      <header className="tabs-topbar panel-card">
        <div className="brand-block">
          <p className="brand-kicker">{t("app.brand")}</p>
          <h1>DJX Studio</h1>
          <p className="muted">{t("app.subtitle")}</p>
        </div>
        <div className="topbar-actions">
          <nav className="tab-nav" aria-label={t("app.tabsAriaLabel")}>
            {TAB_ORDER.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`tab-btn ${activeTab === item.key ? "active" : ""}`}
                onClick={() => setActiveTab(item.key)}
              >
                {t(item.labelKey)}
              </button>
            ))}
          </nav>

          <label className="lang-switch">
            <span>{t("app.lang.label")}</span>
            <select
              value={lang}
              onChange={(event) => {
                setLang(event.target.value as UiLanguage);
              }}
            >
              <option value="en">{t("app.lang.en")}</option>
              <option value="zh">{t("app.lang.zh")}</option>
            </select>
          </label>
        </div>
      </header>

      <main className="tabs-main" aria-live="polite">
        <div className="tab-panel-shell">{activePanel}</div>
      </main>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { fetchSessionEvents, interruptSession, sendSessionMessage, startSession, stopSession } from "../api/session";
import type { SessionEvent } from "../api/types";
import { useSessionStore } from "../store/sessionStore";
import { useI18n } from "../i18n";

type ChatItem =
  | {
      kind: "user" | "assistant";
      key: string;
      seq: number;
      text: string;
      thinking?: string;
    }
  | {
      kind: "tool";
      key: string;
      seq: number;
      tool: string;
      callId: string;
      args: unknown;
      status: "running" | "ok" | "failed";
      summary: string;
      resultPreview: string;
      errorType: string | null;
    }
  | {
      kind: "system";
      key: string;
      seq: number;
      text: string;
    }
  | {
      kind: "reasoning";
      key: string;
      seq: number;
      step: number;
      toolChoice: string;
      thinking: string;
      textPreview: string;
      plannedTools: unknown[];
    };

function mergeEvents(base: SessionEvent[], incoming: SessionEvent[]): SessionEvent[] {
  const bySeq = new Map<number, SessionEvent>();
  for (const item of base) {
    bySeq.set(item.seq, item);
  }
  for (const item of incoming) {
    bySeq.set(item.seq, item);
  }
  return Array.from(bySeq.values()).sort((a, b) => a.seq - b.seq);
}

function toText(value: unknown): string {
  return String(value ?? "").trim();
}

function toPrettyJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

function toSingleLinePreview(text: string, maxLen = 180): string {
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  if (!compact) {
    return "";
  }
  if (compact.length <= maxLen) {
    return compact;
  }
  return `${compact.slice(0, maxLen - 3)}...`;
}

function toolCommandPreview(tool: string, args: Record<string, unknown>): string {
  const name = String(tool || "").trim();
  const getArg = (key: string): string => toText(args[key]);
  if (name === "execute_shell_command") {
    return getArg("command");
  }
  if (name === "execute_python_code") {
    return getArg("code");
  }
  return "";
}

function normalizeForCompare(text: string): string {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function isMostlyDuplicateText(a: string, b: string): boolean {
  const left = normalizeForCompare(a);
  const right = normalizeForCompare(b);
  if (!left || !right) {
    return false;
  }
  if (left === right) {
    return true;
  }
  if (left.includes(right) || right.includes(left)) {
    const minLen = Math.min(left.length, right.length);
    const maxLen = Math.max(left.length, right.length);
    return minLen / maxLen >= 0.75;
  }
  return false;
}

const reflectiveTailPatterns: RegExp[] = [
  /^\s*[·•\-*]?\s*the user (requested|asked)\b/im,
  /^\s*[·•\-*]?\s*i (have )?(successfully )?(completed|finished)\b/im,
  /^\s*[·•\-*]?\s*task (is )?(completed|finished)\b/im,
  /^\s*[·•\-*]?\s*here (is|are) (what )?i (did|have done)\b/im,
  /^\s*[·•\-*]?\s*用户(要求|请求|希望)/m,
  /^\s*[·•\-*]?\s*下面是.*(步骤|总结)/m,
];

function stripReflectiveTail(text: string): { text: string; tail: string } {
  const body = String(text || "").trim();
  if (!body) {
    return { text: "", tail: "" };
  }
  for (const pattern of reflectiveTailPatterns) {
    const matched = pattern.exec(body);
    if (!matched) {
      continue;
    }
    const idx = matched.index;
    if (idx <= 0) {
      continue;
    }
    if (!body.slice(0, idx).includes("\n")) {
      continue;
    }
    const head = body.slice(0, idx).trimEnd();
    const tail = body.slice(idx).trim();
    if (!head || tail.length < 40) {
      continue;
    }
    return { text: head, tail };
  }
  return { text: body, tail: "" };
}

function normalizeAssistantContent(text: string, thinking: string): { text: string; thinking: string } {
  let cleanText = String(text || "");
  let cleanThinking = String(thinking || "").trim();

  const thinkMatch = cleanText.match(/^\s*<think>\s*([\s\S]*?)\s*<\/think>\s*/i);
  if (thinkMatch) {
    if (!cleanThinking) {
      cleanThinking = String(thinkMatch[1] || "").trim();
    }
    cleanText = cleanText.slice(thinkMatch[0].length);
  }

  cleanText = cleanText.replace(/^\s*(?:<\/think>\s*)+/i, "").trim();
  const stripped = stripReflectiveTail(cleanText);
  cleanText = stripped.text;
  // Drop reflective tail entirely instead of moving to thinking.
  // Otherwise it may still be displayed in some clients.
  if (isMostlyDuplicateText(cleanText, cleanThinking)) {
    cleanThinking = "";
  }
  return {
    text: cleanText,
    thinking: cleanThinking,
  };
}

function buildClientMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function isSessionNotFoundError(error: unknown): boolean {
  return String(error ?? "").includes("Session not found");
}

function buildChatItems(
  events: SessionEvent[],
  t: (key: string, params?: Record<string, string | number | boolean | null | undefined>) => string,
): ChatItem[] {
  const rows = [...events].sort((a, b) => a.seq - b.seq);
  const items: ChatItem[] = [];
  const toolIndexByCallId = new Map<string, number>();

  for (const event of rows) {
    const payload = event.payload || {};

    if (event.type === "user_message") {
      items.push({
        kind: "user",
        key: `u_${event.seq}`,
        seq: event.seq,
        text: toText(payload.text),
      });
      continue;
    }

    if (event.type === "assistant_message") {
      const normalized = normalizeAssistantContent(toText(payload.text), toText(payload.thinking));
      items.push({
        kind: "assistant",
        key: `a_${event.seq}`,
        seq: event.seq,
        text: normalized.text,
        thinking: normalized.thinking,
      });
      continue;
    }

    if (event.type === "reasoning_step") {
      const rawStep = Number(payload.step ?? 0);
      const step = Number.isFinite(rawStep) && rawStep > 0 ? rawStep : 0;
      const plannedTools = Array.isArray(payload.planned_tools) ? payload.planned_tools : [];
      items.push({
        kind: "reasoning",
        key: `r_${event.seq}`,
        seq: event.seq,
        step,
        toolChoice: toText(payload.tool_choice),
        thinking: toText(payload.thinking),
        textPreview: toText(payload.text_preview),
        plannedTools,
      });
      continue;
    }

    if (event.type === "session_started") {
      items.push({
        kind: "system",
        key: `s_${event.seq}`,
        seq: event.seq,
        text: t("chat.system.started"),
      });
      continue;
    }

    if (event.type === "session_stopped") {
      items.push({
        kind: "system",
        key: `s_${event.seq}`,
        seq: event.seq,
        text: t("chat.system.stopped"),
      });
      continue;
    }

    if (event.type === "session_error") {
      items.push({
        kind: "system",
        key: `s_${event.seq}`,
        seq: event.seq,
        text: t("chat.system.error", { error: toText(payload.error) }),
      });
      continue;
    }

    if (event.type === "interrupt_requested") {
      items.push({
        kind: "system",
        key: `s_${event.seq}`,
        seq: event.seq,
        text: t("chat.system.interruptRequested"),
      });
      continue;
    }

    if (event.type === "interrupt_ack") {
      items.push({
        kind: "system",
        key: `s_${event.seq}`,
        seq: event.seq,
        text: t("chat.system.interruptAck"),
      });
      continue;
    }

    if (event.type === "interrupt_ignored") {
      items.push({
        kind: "system",
        key: `s_${event.seq}`,
        seq: event.seq,
        text: t("chat.system.interruptIgnored"),
      });
      continue;
    }

    if (event.type === "tool_start") {
      const callId = toText(payload.call_id) || `call_${event.seq}`;
      const item: ChatItem = {
        kind: "tool",
        key: `t_${callId}`,
        seq: event.seq,
        tool: toText(payload.tool) || "tool",
        callId,
        args: payload.args ?? {},
        status: "running",
        summary: "",
        resultPreview: "",
        errorType: null,
      };
      toolIndexByCallId.set(callId, items.length);
      items.push(item);
      continue;
    }

    if (event.type === "tool_end") {
      const callId = toText(payload.call_id) || `call_${event.seq}`;
      const idx = toolIndexByCallId.get(callId);
      const status: "ok" | "failed" = Boolean(payload.ok) ? "ok" : "failed";
      const summary = toText(payload.summary);
      const resultPreview = toText(payload.result_preview);
      const errorType = toText(payload.error_type) || null;

      if (idx === undefined) {
        items.push({
          kind: "tool",
          key: `t_${callId}_${event.seq}`,
          seq: event.seq,
          tool: toText(payload.tool) || "tool",
          callId,
          args: {},
          status,
          summary,
          resultPreview,
          errorType,
        });
      } else {
        const old = items[idx];
        if (old.kind === "tool") {
          items[idx] = {
            ...old,
            status,
            summary,
            resultPreview,
            errorType,
          };
        }
      }
    }

    // Compatibility with tool event payload names from some AgentScope/OpenAI traces.
    if (event.type === "tool_use") {
      const callId = toText(payload.id) || `call_${event.seq}`;
      const item: ChatItem = {
        kind: "tool",
        key: `t_${callId}`,
        seq: event.seq,
        tool: toText(payload.name || payload.tool) || "tool",
        callId,
        args: payload.input ?? payload.args ?? {},
        status: "running",
        summary: "",
        resultPreview: "",
        errorType: null,
      };
      toolIndexByCallId.set(callId, items.length);
      items.push(item);
      continue;
    }

    if (event.type === "tool_result") {
      const callId = toText(payload.id || payload.call_id) || `call_${event.seq}`;
      const idx = toolIndexByCallId.get(callId);
      const outputText = toText(payload.output);
      const status: "ok" | "failed" = payload.error ? "failed" : "ok";
      if (idx === undefined) {
        items.push({
          kind: "tool",
          key: `t_${callId}_${event.seq}`,
          seq: event.seq,
          tool: toText(payload.name || payload.tool) || "tool",
          callId,
          args: payload.input ?? payload.args ?? {},
          status,
          summary: outputText.slice(0, 240),
          resultPreview: outputText,
          errorType: payload.error ? "tool_result_error" : null,
        });
      } else {
        const old = items[idx];
        if (old.kind === "tool") {
          items[idx] = {
            ...old,
            status,
            summary: outputText.slice(0, 240),
            resultPreview: outputText,
            errorType: payload.error ? "tool_result_error" : null,
          };
        }
      }
      continue;
    }
  }

  return items;
}

export default function ChatPanel() {
  const { t } = useI18n();
  const setSession = useSessionStore((state) => state.setSession);
  const setContextFromPayload = useSessionStore((state) => state.setContextFromPayload);
  const clearSessionStore = useSessionStore((state) => state.clearSession);

  const [profileName, setProfileName] = useState("default");
  const [datasetPath, setDatasetPath] = useState("");
  const [exportPath, setExportPath] = useState("");
  const [sessionId, setSessionId] = useState<string>("");
  const [nextSeq, setNextSeq] = useState(0);
  const [events, setEvents] = useState<SessionEvent[]>([]);
  const [input, setInput] = useState("");
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const messageBoxRef = useRef<HTMLDivElement | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const sendingRef = useRef(false);

  const startMutation = useMutation({
    mutationFn: startSession,
    onSuccess: (payload) => {
      setSessionId(payload.session_id);
      setSession(payload.session_id);
      setContextFromPayload((payload.context ?? {}) as Record<string, unknown>);
      setEvents(payload.events ?? []);
      setNextSeq(payload.events.length > 0 ? payload.events[payload.events.length - 1].seq : 0);
      setExpandedTools({});
      setError("");
    },
    onError: (err) => {
      setError(t("chat.error.startFailed", { error: String(err) }));
    },
  });

  const sendMutation = useMutation({
    mutationFn: sendSessionMessage,
    retry: 0,
    onSuccess: (payload) => {
      setEvents((prev) => mergeEvents(prev, payload.events ?? []));
      setNextSeq(payload.next_seq);
      setContextFromPayload((payload.context ?? {}) as Record<string, unknown>);
      if (payload.stop) {
        setSessionId("");
        clearSessionStore();
      }
      setError("");
    },
    onError: (err) => {
      if (isSessionNotFoundError(err)) {
        setSessionId("");
        setNextSeq(0);
        clearSessionStore();
        setError(t("chat.error.expired"));
        return;
      }
      setError(t("chat.error.sendFailed", { error: String(err) }));
    },
  });

  const stopMutation = useMutation({
    mutationFn: stopSession,
    onSuccess: () => {
      setSessionId("");
      setNextSeq(0);
      clearSessionStore();
    },
    onError: (err) => {
      setError(t("chat.error.stopFailed", { error: String(err) }));
    },
  });

  const interruptMutation = useMutation({
    mutationFn: interruptSession,
    onError: (err) => {
      setError(t("chat.error.interruptFailed", { error: String(err) }));
    },
  });

  useEffect(() => {
    if (!sessionId) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const payload = await fetchSessionEvents({
          session_id: sessionId,
          after: nextSeq,
          limit: 200,
        });
        if (payload.events.length > 0) {
          setEvents((prev) => mergeEvents(prev, payload.events));
          setNextSeq(payload.next_seq);
        }
      } catch (err) {
        if (isSessionNotFoundError(err)) {
          setSessionId("");
          setNextSeq(0);
          clearSessionStore();
          setError(t("chat.error.expired"));
          return;
        }
        setError(t("chat.error.fetchFailed", { error: String(err) }));
      }
    }, 1200);

    return () => {
      window.clearInterval(timer);
    };
  }, [sessionId, nextSeq]);

  const chatItems = useMemo(() => buildChatItems(events, t), [events, t]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const container = messageBoxRef.current;
      if (container) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: "auto",
        });
      }
      messageEndRef.current?.scrollIntoView({
        behavior: "auto",
        block: "end",
      });
    });
    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [nextSeq, chatItems.length, sendMutation.isPending]);

  const onStart = async () => {
    await startMutation.mutateAsync({
      profile_name: profileName.trim() || "default",
      dataset_path: datasetPath.trim() || undefined,
      export_path: exportPath.trim() || undefined,
      verbose: false,
    });
  };

  const onSend = async () => {
    if (!sessionId) {
      setError(t("chat.error.notStarted"));
      return;
    }
    if (sendMutation.isPending || sendingRef.current) {
      return;
    }
    const message = input.trim();
    if (!message) {
      return;
    }
    setInput("");
    sendingRef.current = true;
    try {
      await sendMutation.mutateAsync({
        session_id: sessionId,
        message,
        client_message_id: buildClientMessageId(),
      });
    } finally {
      sendingRef.current = false;
    }
  };

  const onStop = async () => {
    if (!sessionId) {
      return;
    }
    await stopMutation.mutateAsync({
      session_id: sessionId,
    });
  };

  const onInterrupt = async () => {
    if (!sessionId || !sendMutation.isPending) {
      return;
    }
    await interruptMutation.mutateAsync({
      session_id: sessionId,
    });
  };

  return (
    <section className="panel-card chat-panel">
      <header className="panel-head">
        <h2>{t("chat.title")}</h2>
        <p>{t("chat.description")}</p>
        <p className="muted">{t("chat.sessionId", { value: sessionId || "-" })}</p>
      </header>

      <div className="chat-controls">
        <input value={profileName} onChange={(e) => setProfileName(e.target.value)} placeholder={t("chat.input.profile")} />
        <input
          value={datasetPath}
          onChange={(e) => setDatasetPath(e.target.value)}
          placeholder={t("chat.input.datasetOptional")}
        />
        <input value={exportPath} onChange={(e) => setExportPath(e.target.value)} placeholder={t("chat.input.exportOptional")} />
        <button onClick={onStart} disabled={Boolean(sessionId) || startMutation.isPending}>
          {startMutation.isPending ? t("chat.btn.starting") : t("chat.btn.start")}
        </button>
        <button onClick={onStop} disabled={!sessionId || stopMutation.isPending}>
          {t("chat.btn.stop")}
        </button>
      </div>

      <div className="chat-layout">
        <div className="message-column">
          <div className="messages-box" ref={messageBoxRef}>
            {chatItems.length === 0 ? <p className="muted">{t("chat.empty.noMessage")}</p> : null}

            {chatItems.map((item) => {
              switch (item.kind) {
                case "user":
                  return (
                    <article key={item.key} className="message-item user">
                      <strong>{t("chat.role.you")}</strong>
                      <div className="message-content markdown-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.text}</ReactMarkdown>
                      </div>
                    </article>
                  );
                case "assistant":
                  if (!item.text.trim()) {
                    return (
                      <article key={item.key} className="system-item">
                        {t("chat.assistant.empty")}
                      </article>
                    );
                  }
                  return (
                    <article key={item.key} className="message-item assistant">
                      <strong>{t("chat.role.agent")}</strong>
                      {item.thinking ? (
                        <details className="thinking-block">
                          <summary>{t("chat.block.thinking")}</summary>
                          <div className="message-content markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.thinking}</ReactMarkdown>
                          </div>
                        </details>
                      ) : null}
                      <div className="message-content markdown-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.text}</ReactMarkdown>
                      </div>
                    </article>
                  );
                case "system":
                  return (
                    <article key={item.key} className="system-item">
                      {item.text}
                    </article>
                  );
                case "reasoning": {
                  const plannedCount = item.plannedTools.length;
                  const title = item.step > 0 ? t("chat.reasoning.step", { step: item.step }) : t("chat.reasoning");
                  const showTextPreview = Boolean(item.textPreview) && !isMostlyDuplicateText(item.thinking, item.textPreview);
                  return (
                    <article key={item.key} className="reasoning-item">
                      <details className="reasoning-block">
                        <summary>
                          {title}
                          {item.toolChoice ? ` · ${t("chat.reasoning.toolChoice", { toolChoice: item.toolChoice })}` : ""}
                          {plannedCount > 0 ? ` · ${t("chat.reasoning.planned", { count: plannedCount })}` : ""}
                        </summary>
                        {item.thinking ? (
                          <div className="message-content markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.thinking}</ReactMarkdown>
                          </div>
                        ) : null}
                        {showTextPreview ? (
                          <div className="message-content markdown-body">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.textPreview}</ReactMarkdown>
                          </div>
                        ) : null}
                        {plannedCount > 0 ? <pre>{toPrettyJson(item.plannedTools)}</pre> : null}
                      </details>
                    </article>
                  );
                }
                case "tool": {
                  const statusText =
                    item.status === "ok"
                      ? t("chat.tool.status.ok")
                      : item.status === "failed"
                        ? t("chat.tool.status.failed")
                        : t("chat.tool.status.running");
                  const expanded = Boolean(expandedTools[item.key]);
                  const argsObject =
                    item.args && typeof item.args === "object" && !Array.isArray(item.args)
                      ? (item.args as Record<string, unknown>)
                      : {};
                  const argCount = Object.keys(argsObject).length;
                  const toolLabel = item.tool.trim() || "tool";
                  const commandPreview = toolCommandPreview(toolLabel, argsObject);
                  const collapsedPreview = toSingleLinePreview(
                    commandPreview || item.summary || item.resultPreview,
                  );
                  return (
                    <article key={item.key} className={`tool-item ${item.status}`}>
                      <button
                        type="button"
                        className="tool-head"
                        aria-expanded={expanded}
                        onClick={() =>
                          setExpandedTools((prev) => ({
                            ...prev,
                            [item.key]: !expanded,
                          }))
                        }
                      >
                        <span className="tool-head-left">
                          <span className={`tool-chevron ${expanded ? "open" : ""}`}>›</span>
                          <span className="tool-title">{t("chat.tool.label", { tool: toolLabel })}</span>
                          <span className="tool-meta">
                            {(argCount > 0 ? t("chat.tool.argsCount", { count: argCount }) : t("chat.tool.argsNone")) +
                              ` · ${expanded ? t("chat.tool.collapse") : t("chat.tool.expand")}`}
                          </span>
                        </span>
                        <span className={`tool-status ${item.status}`}>{statusText}</span>
                      </button>

                      {!expanded ? (
                        <div className="tool-collapsed-hint">
                          {collapsedPreview || t("chat.tool.hint")}
                        </div>
                      ) : null}

                      {expanded ? (
                        <div className="tool-body">
                          <p className="tool-meta">{t("chat.tool.callId", { value: item.callId })}</p>
                          {commandPreview ? <p className="tool-summary"><code>{commandPreview}</code></p> : null}
                          {item.summary ? <p className="tool-summary">{item.summary}</p> : null}
                          {item.errorType ? <p className="tool-error">{t("chat.tool.errorType", { value: item.errorType })}</p> : null}
                          <details className="tool-args-block">
                            <summary>{argCount > 0 ? t("chat.tool.argsSummary", { count: argCount }) : t("chat.tool.argsSummaryNone")}</summary>
                            <pre>{toPrettyJson(item.args ?? {})}</pre>
                          </details>
                          {item.resultPreview ? (
                            <details className="tool-result-block">
                              <summary>{t("chat.tool.result")}</summary>
                              <pre>{item.resultPreview}</pre>
                            </details>
                          ) : null}
                        </div>
                      ) : null}
                    </article>
                  );
                }
                default:
                  return null;
              }
            })}

            <div ref={messageEndRef} className="message-end-anchor" />
          </div>

          <div className="composer-row">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={sessionId ? t("chat.input.prompt") : t("chat.input.startFirst")}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !(e.nativeEvent as KeyboardEvent).isComposing) {
                  e.preventDefault();
                  void onSend();
                }
              }}
            />
            <button onClick={onSend} disabled={!sessionId || sendMutation.isPending}>
              {sendMutation.isPending ? t("chat.btn.sending") : t("chat.btn.send")}
            </button>
            <button onClick={onInterrupt} disabled={!sessionId || !sendMutation.isPending || interruptMutation.isPending}>
              {interruptMutation.isPending ? t("chat.btn.interrupting") : t("chat.btn.interrupt")}
            </button>
          </div>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}

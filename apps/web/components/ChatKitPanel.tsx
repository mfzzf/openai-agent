"use client";

import { useCallback, useEffect } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { useChatKitSession } from "@/hooks/useChatKitSession";
import { useSandboxActions } from "@/hooks/useSandboxActions";
import { useWorkspaceStore, type ToolEvent } from "@/hooks/useWorkspaceStore";

const TOOL_REDACT_KEYS = new Set([
  "streamUrl",
  "authKey",
  "imageBase64",
  "data",
  "fileData",
  "file_data",
]);

function sanitizeToolPayload(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((entry) => sanitizeToolPayload(entry));
  }
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
      output[key] = TOOL_REDACT_KEYS.has(key)
        ? "[redacted]"
        : sanitizeToolPayload(entry);
    }
    return output;
  }
  return value;
}

export function ChatKitPanel(): JSX.Element {
  const { getClientSecret } = useChatKitSession();
  const setThreadId = useWorkspaceStore((state) => state.setThreadId);
  const setSandboxThreadId = useWorkspaceStore((state) => state.setSandboxThreadId);
  const setActiveTab = useWorkspaceStore((state) => state.setActiveTab);
  const setDesktop = useWorkspaceStore((state) => state.setDesktop);
  const addEvent = useWorkspaceStore((state) => state.trace.addEvent);
  const notify = useWorkspaceStore((state) => state.addNotice);
  const setToolEventEmitter = useWorkspaceStore(
    (state) => state.setToolEventEmitter
  );
  const {
    startDesktop,
    stopDesktop,
    runPython,
    runDesktopAction,
    takeDesktopScreenshot,
    setDesktopTimeout,
  } = useSandboxActions();

  const chatkitApiUrl = process.env.NEXT_PUBLIC_CHATKIT_API_URL;
  const chatkitDomainKey =
    process.env.NEXT_PUBLIC_CHATKIT_DOMAIN_KEY ?? "local-dev";
  const resolvedUploadUrl = () => {
    if (!chatkitApiUrl) {
      return "";
    }
    if (chatkitApiUrl.includes("://")) {
      return new URL("/files", chatkitApiUrl).toString();
    }
    const trimmed = chatkitApiUrl.replace(/\/chatkit\/?$/, "");
    return `${trimmed}/files`;
  };
  const chatkitUploadUrl =
    process.env.NEXT_PUBLIC_CHATKIT_UPLOAD_URL ??
    resolvedUploadUrl();

  const { control, sendCustomAction } = useChatKit({
    api: chatkitApiUrl
      ? {
          url: chatkitApiUrl,
          domainKey: chatkitDomainKey,
          uploadStrategy: {
            type: "direct",
            uploadUrl: chatkitUploadUrl,
          },
        }
      : {
          async getClientSecret(currentClientSecret) {
            return await getClientSecret(currentClientSecret);
          },
        },
    composer: {
      attachments: {
        enabled: Boolean(chatkitApiUrl),
      },
    },
    onThreadChange(event) {
      setThreadId(event.threadId ?? null);
      if (event.threadId) {
        const current = useWorkspaceStore.getState().sandboxThreadId;
        if (!current) {
          setSandboxThreadId(event.threadId);
        }
      }
      addEvent({
        ts: Date.now(),
        type: "info",
        title: "thread.change",
        detail: { threadId: event.threadId },
      });
    },
    onError(event) {
      addEvent({
        ts: Date.now(),
        type: "error",
        title: "chatkit.error",
        detail: event,
      });
    },
    onClientTool: async (toolCall) => {
      addEvent({
        ts: Date.now(),
        type: "tool",
        title: `tool:${toolCall.name}`,
        detail: toolCall.params,
      });

      try {
        switch (toolCall.name) {
          case "ui.openTab": {
            const tab = toolCall.params?.tab as
              | "desktop"
              | "python"
              | "trace"
              | undefined;
            if (tab) {
              setActiveTab(tab);
            }
            return { ok: true };
          }
          case "ui.openDesktopPanel": {
            const streamUrl = toolCall.params?.streamUrl as string | undefined;
            if (streamUrl) {
              setDesktop({ streamUrl, status: "ready" });
            }
            setActiveTab("desktop");
            return { ok: true };
          }
          case "ui.openPythonPanel": {
            setActiveTab("python");
            return { ok: true };
          }
          case "ui.notify": {
            const level = toolCall.params?.level as string | undefined;
            const message = toolCall.params?.message as string | undefined;
            if (message) {
              const normalized =
                level === "error" || level === "warn" || level === "info"
                  ? level
                  : "info";
              notify(normalized, message);
            }
            return { ok: true };
          }
          case "sandbox.desktop.start": {
            const viewOnly = Boolean(toolCall.params?.viewOnly ?? false);
            const requireAuth = Boolean(toolCall.params?.requireAuth ?? true);
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            const session = await startDesktop({
              viewOnly,
              requireAuth,
              threadId: toolThreadId,
              source: "chatkit",
            });
            setActiveTab("desktop");
            return {
              ok: true,
              streamUrl: session.streamUrl,
              viewOnly: session.viewOnly,
            };
          }
          case "sandbox.desktop.stop": {
            await stopDesktop({ source: "chatkit" });
            return { ok: true };
          }
          case "sandbox.desktop.setTimeout": {
            const timeoutSeconds = toolCall.params?.timeoutSeconds as
              | number
              | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (typeof timeoutSeconds !== "number") {
              return { ok: false, error: { message: "Missing timeoutSeconds" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            const session = await setDesktopTimeout(timeoutSeconds, {
              threadId: toolThreadId,
              source: "chatkit",
            });
            return {
              ok: true,
              timeoutSeconds: session.timeoutSeconds,
              expiresAt: session.expiresAt,
            };
          }
          case "sandbox.code.run": {
            const code = toolCall.params?.code as string | undefined;
            const language = toolCall.params?.language as
              | "python"
              | "go"
              | "js"
              | "rust"
              | undefined;
            const timeoutSeconds = toolCall.params?.timeoutSeconds as
              | number
              | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (!code) {
              return { ok: false, error: { message: "Missing code" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            const result = await runPython(
              code,
              timeoutSeconds,
              language,
              toolThreadId,
              { source: "chatkit" }
            );
            setActiveTab("python");
            return { ok: true, result };
          }
          case "sandbox.desktop.click": {
            const x = toolCall.params?.x as number | undefined;
            const y = toolCall.params?.y as number | undefined;
            const button = toolCall.params?.button as
              | "left"
              | "right"
              | "middle"
              | undefined;
            const double = toolCall.params?.double as boolean | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (typeof x !== "number" || typeof y !== "number") {
              return { ok: false, error: { message: "Missing click coordinates" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "click", x, y, button, double },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.type": {
            const text = toolCall.params?.text as string | undefined;
            const chunkSize = toolCall.params?.chunkSize as number | undefined;
            const delayInMs = toolCall.params?.delayInMs as number | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (!text) {
              return { ok: false, error: { message: "Missing text" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "type", text, chunkSize, delayInMs },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.press": {
            const keys = toolCall.params?.keys as string[] | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (!Array.isArray(keys) || keys.length === 0) {
              return { ok: false, error: { message: "Missing keys" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "press", keys },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.wait": {
            const ms = toolCall.params?.ms as number | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (typeof ms !== "number") {
              return { ok: false, error: { message: "Missing ms" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "wait", ms },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.scroll": {
            const direction = toolCall.params?.direction as
              | "up"
              | "down"
              | undefined;
            const amount = toolCall.params?.amount as number | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "scroll", direction, amount },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.moveMouse": {
            const x = toolCall.params?.x as number | undefined;
            const y = toolCall.params?.y as number | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (typeof x !== "number" || typeof y !== "number") {
              return {
                ok: false,
                error: { message: "Missing mouse coordinates" },
              };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "moveMouse", x, y },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.drag": {
            const fromX = toolCall.params?.fromX as number | undefined;
            const fromY = toolCall.params?.fromY as number | undefined;
            const toX = toolCall.params?.toX as number | undefined;
            const toY = toolCall.params?.toY as number | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (
              typeof fromX !== "number" ||
              typeof fromY !== "number" ||
              typeof toX !== "number" ||
              typeof toY !== "number"
            ) {
              return { ok: false, error: { message: "Missing drag coordinates" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            await runDesktopAction(
              { action: "drag", fromX, fromY, toX, toY },
              { threadId: toolThreadId, source: "chatkit" }
            );
            setActiveTab("desktop");
            return { ok: true };
          }
          case "sandbox.desktop.screenshot": {
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            const includeCursor = toolCall.params?.includeCursor as
              | boolean
              | undefined;
            const includeScreenSize = toolCall.params?.includeScreenSize as
              | boolean
              | undefined;
            if (toolThreadId) {
              setThreadId(toolThreadId);
              setSandboxThreadId(toolThreadId);
            }
            const screenshot = await takeDesktopScreenshot({
              threadId: toolThreadId,
              includeCursor,
              includeScreenSize,
            });
            setActiveTab("desktop");
            return { ok: true, ...screenshot };
          }
          default:
            const response = {
              ok: false,
              error: { message: "Unknown tool" },
            };
            return response;
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Tool execution failed";
        addEvent({
          ts: Date.now(),
          type: "error",
          title: `tool:${toolCall.name}:error`,
          detail: { message },
        });
        const response = { ok: false, error: { message } };
        return response;
      }
    },
  });

  const emitChatkitToolEvent = useCallback(
    async (event: ToolEvent) => {
      if (!chatkitApiUrl) {
        return;
      }
      try {
        await sendCustomAction({
          type: "tool",
          payload: {
            type: "tool",
            tool: event.tool,
            params: sanitizeToolPayload(event.params ?? {}),
            result: sanitizeToolPayload(event.result),
            status: event.status,
            source: event.source,
            callId: event.callId,
          },
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Failed to record tool event";
        addEvent({
          ts: Date.now(),
          type: "error",
          title: "tool:send_error",
          detail: { message },
        });
      }
    },
    [addEvent, chatkitApiUrl, sendCustomAction]
  );

  useEffect(() => {
    if (!chatkitApiUrl) {
      setToolEventEmitter(null);
      return;
    }
    setToolEventEmitter(emitChatkitToolEvent);
    return () => setToolEventEmitter(null);
  }, [chatkitApiUrl, emitChatkitToolEvent, setToolEventEmitter]);

  return (
    <div className="chatkit-root">
      <ChatKit control={control} className="chatkit-root" />
    </div>
  );
}

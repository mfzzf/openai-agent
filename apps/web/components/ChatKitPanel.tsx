"use client";

import { useEffect } from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { useChatKitSession } from "@/hooks/useChatKitSession";
import { useSandboxActions } from "@/hooks/useSandboxActions";
import { useWorkspaceStore, type ToolEvent } from "@/hooks/useWorkspaceStore";

export function ChatKitPanel(): JSX.Element {
  const { getClientSecret } = useChatKitSession();
  const setThreadId = useWorkspaceStore((state) => state.setThreadId);
  const setActiveTab = useWorkspaceStore((state) => state.setActiveTab);
  const setDesktop = useWorkspaceStore((state) => state.setDesktop);
  const addEvent = useWorkspaceStore((state) => state.trace.addEvent);
  const notify = useWorkspaceStore((state) => state.addNotice);
  const setToolEventEmitter = useWorkspaceStore(
    (state) => state.setToolEventEmitter
  );
  const { startDesktop, stopDesktop, runPython } = useSandboxActions();

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

  const toolRedactKeys = new Set(["streamUrl", "authKey"]);
  const sanitizeToolPayload = (value: unknown): unknown => {
    if (Array.isArray(value)) {
      return value.map((entry) => sanitizeToolPayload(entry));
    }
    if (value && typeof value === "object") {
      const output: Record<string, unknown> = {};
      for (const [key, entry] of Object.entries(
        value as Record<string, unknown>
      )) {
        output[key] = toolRedactKeys.has(key)
          ? "[redacted]"
          : sanitizeToolPayload(entry);
      }
      return output;
    }
    return value;
  };

  const emitChatkitToolEvent = async (event: ToolEvent) => {
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
  };

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
          case "sandbox.python.run": {
            const code = toolCall.params?.code as string | undefined;
            const timeoutSeconds = toolCall.params?.timeoutSeconds as
              | number
              | undefined;
            const toolThreadId = toolCall.params?.threadId as string | undefined;
            if (!code) {
              return { ok: false, error: { message: "Missing code" } };
            }
            if (toolThreadId) {
              setThreadId(toolThreadId);
            }
            const result = await runPython(
              code,
              timeoutSeconds,
              toolThreadId,
              { source: "chatkit" }
            );
            setActiveTab("python");
            return { ok: true, result };
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

  useEffect(() => {
    if (!chatkitApiUrl) {
      setToolEventEmitter(null);
      return;
    }
    setToolEventEmitter(() => emitChatkitToolEvent);
    return () => setToolEventEmitter(null);
  }, [chatkitApiUrl, emitChatkitToolEvent, setToolEventEmitter]);

  return (
    <div className="chatkit-root">
      <ChatKit control={control} className="chatkit-root" />
    </div>
  );
}

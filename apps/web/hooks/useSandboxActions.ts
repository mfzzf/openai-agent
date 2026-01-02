"use client";

import type { DesktopSandboxSession, PythonRunResult } from "@/lib/types/sandbox";
import { postJson } from "@/lib/apiClient";
import { useWorkspaceStore } from "@/hooks/useWorkspaceStore";

export function useSandboxActions() {
  const threadId = useWorkspaceStore((state) => state.threadId);
  const setDesktop = useWorkspaceStore((state) => state.setDesktop);
  const setPython = useWorkspaceStore((state) => state.setPython);
  const setPythonCode = useWorkspaceStore((state) => state.setPythonCode);
  const addEvent = useWorkspaceStore((state) => state.trace.addEvent);
  const emitToolEvent = useWorkspaceStore((state) => state.emitToolEvent);

  const ensureThreadId = (override?: string) => {
    if (override) {
      return override;
    }
    if (!threadId) {
      throw new Error("Thread is not ready yet.");
    }
    return threadId;
  };

  const startDesktop = async (opts?: {
    viewOnly?: boolean;
    requireAuth?: boolean;
    threadId?: string;
    source?: "chatkit" | "manual" | "system";
  }): Promise<DesktopSandboxSession> => {
    const activeThreadId = ensureThreadId(opts?.threadId);
    setDesktop({ status: "starting", error: undefined });

    try {
      const response = await postJson<{
        ok: true;
        session: DesktopSandboxSession;
      }>("/api/sandbox/desktop/start", {
        threadId: activeThreadId,
        viewOnly: opts?.viewOnly ?? false,
        requireAuth: opts?.requireAuth ?? true,
      });

      setDesktop({
        status: "ready",
        streamUrl: response.session.streamUrl ?? null,
        viewOnly: response.session.viewOnly,
        error: undefined,
      });

      addEvent({
        ts: Date.now(),
        type: "info",
        title: "desktop.started",
        detail: response.session,
      });

      const source = opts?.source ?? "manual";
      if (source !== "chatkit") {
        void emitToolEvent({
          tool: "sandbox.desktop.start",
          params: {
            threadId: activeThreadId,
            viewOnly: opts?.viewOnly ?? false,
            requireAuth: opts?.requireAuth ?? true,
          },
          result: {
            ok: true,
            viewOnly: response.session.viewOnly,
          },
          status: "success",
          source,
        });
      }

      return response.session;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Desktop start failed";
      setDesktop({ status: "error", error: message });
      const source = opts?.source ?? "manual";
      if (source !== "chatkit") {
        void emitToolEvent({
          tool: "sandbox.desktop.start",
          params: {
            threadId: activeThreadId,
            viewOnly: opts?.viewOnly ?? false,
            requireAuth: opts?.requireAuth ?? true,
          },
          result: { ok: false, error: { message } },
          status: "error",
          source,
        });
      }
      throw error;
    }
  };

  const stopDesktop = async (opts?: {
    threadId?: string;
    source?: "chatkit" | "manual" | "system";
  }): Promise<void> => {
    const activeThreadId = ensureThreadId(opts?.threadId);
    try {
      await postJson<{ ok: true; stopped: boolean }>(
        "/api/sandbox/desktop/stop",
        { threadId: activeThreadId }
      );
      setDesktop({ status: "idle", streamUrl: null });
      addEvent({ ts: Date.now(), type: "info", title: "desktop.stopped" });
      const source = opts?.source ?? "manual";
      if (source !== "chatkit") {
        void emitToolEvent({
          tool: "sandbox.desktop.stop",
          params: { threadId: activeThreadId },
          result: { ok: true },
          status: "success",
          source,
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Desktop stop failed";
      setDesktop({ status: "error", error: message });
      const source = opts?.source ?? "manual";
      if (source !== "chatkit") {
        void emitToolEvent({
          tool: "sandbox.desktop.stop",
          params: { threadId: activeThreadId },
          result: { ok: false, error: { message } },
          status: "error",
          source,
        });
      }
      throw error;
    }
  };

  const runPython = async (
    code: string,
    timeoutSeconds?: number,
    threadIdOverride?: string,
    opts?: { source?: "chatkit" | "manual" | "system" }
  ): Promise<PythonRunResult> => {
    const activeThreadId = ensureThreadId(threadIdOverride);
    setPythonCode(code);
    setPython({ status: "running", error: undefined });

    try {
      const response = await postJson<{ ok: true; result: PythonRunResult }>(
        "/api/sandbox/python/run",
        {
          threadId: activeThreadId,
          code,
          timeoutSeconds,
        }
      );

      setPython({ status: "ready", lastResult: response.result, error: undefined });
      addEvent({ ts: Date.now(), type: "info", title: "python.run" });
      const status = response.result?.error ? "error" : "success";
      const source = opts?.source ?? "manual";
      if (source !== "chatkit") {
        void emitToolEvent({
          tool: "sandbox.python.run",
          params: {
            threadId: activeThreadId,
            code,
            timeoutSeconds,
          },
          result: response.result,
          status,
          source,
        });
      }
      return response.result;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Python run failed";
      setPython({ status: "error", error: message });
      const source = opts?.source ?? "manual";
      if (source !== "chatkit") {
        void emitToolEvent({
          tool: "sandbox.python.run",
          params: {
            threadId: activeThreadId,
            code,
            timeoutSeconds,
          },
          result: { ok: false, error: { message } },
          status: "error",
          source,
        });
      }
      throw error;
    }
  };

  return { startDesktop, stopDesktop, runPython };
}

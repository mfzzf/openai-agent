"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatKitPanel } from "@/components/ChatKitPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PythonPanel } from "@/components/PythonPanel";
import { RunTracePanel } from "@/components/RunTracePanel";
import { Toolbar } from "@/components/Toolbar";
import { VncPanel } from "@/components/VncPanel";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { useSandboxActions } from "@/hooks/useSandboxActions";
import { useWorkspaceStore } from "@/hooks/useWorkspaceStore";

const DEFAULT_DESKTOP_TIMEOUT_SECONDS = 30 * 60;
const DESKTOP_EXTEND_STEP_SECONDS = 30 * 60;
const DESKTOP_MAX_TIMEOUT_SECONDS = 6 * 60 * 60;

function formatRemaining(seconds: number): string {
  const clamped = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const secs = clamped % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function WorkspaceShell() {
  const activeTab = useWorkspaceStore((state) => state.activeTab);
  const setActiveTab = useWorkspaceStore((state) => state.setActiveTab);
  const sandboxThreadId = useWorkspaceStore((state) => state.sandboxThreadId);
  const desktop = useWorkspaceStore((state) => state.desktop);
  const python = useWorkspaceStore((state) => state.python);
  const pythonCode = useWorkspaceStore((state) => state.python.code);
  const pythonLanguage = useWorkspaceStore((state) => state.python.language);
  const setPythonCode = useWorkspaceStore((state) => state.setPythonCode);
  const setPythonLanguage = useWorkspaceStore((state) => state.setPythonLanguage);
  const trace = useWorkspaceStore((state) => state.trace);
  const { startDesktop, stopDesktop, runPython, getDesktopStatus, setDesktopTimeout } =
    useSandboxActions();

  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!sandboxThreadId) {
      return;
    }

    if (desktop.status === "idle") {
      return;
    }

    const refresh = async () => {
      try {
        await getDesktopStatus({ threadId: sandboxThreadId });
      } catch {
        // Ignore status polling errors.
      }
    };

    void refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, [desktop.status, getDesktopStatus, sandboxThreadId]);

  const desktopTimeLeft = useMemo(() => {
    if (!desktop.expiresAt) {
      return null;
    }
    const remaining = Math.max(0, Math.floor((desktop.expiresAt - now) / 1000));
    return formatRemaining(remaining);
  }, [desktop.expiresAt, now]);

  const canExtendDesktop = Boolean(sandboxThreadId && desktop.expiresAt);
  const handleExtendDesktop = () => {
    if (!canExtendDesktop) {
      return;
    }
    const currentTimeout = desktop.timeoutSeconds ?? DEFAULT_DESKTOP_TIMEOUT_SECONDS;
    const nextTimeout = Math.min(
      currentTimeout + DESKTOP_EXTEND_STEP_SECONDS,
      DESKTOP_MAX_TIMEOUT_SECONDS
    );
    void setDesktopTimeout(nextTimeout).catch(() => {
      // Errors are surfaced via the workspace store.
    });
  };

  return (
    <WorkspaceLayout
      left={
        <ErrorBoundary>
          <ChatKitPanel />
        </ErrorBoundary>
      }
      right={
        <div className="workspace-right">
          <Toolbar
            activeTab={activeTab}
            onTabChange={setActiveTab}
            desktopStatus={desktop.status}
            pythonStatus={python.status}
            desktopTimeLeft={desktopTimeLeft}
            onExtendDesktop={handleExtendDesktop}
            extendDesktopDisabled={!canExtendDesktop}
          />
          {activeTab === "desktop" && (
            <VncPanel
              streamUrl={desktop.streamUrl}
              viewOnly={desktop.viewOnly}
              error={desktop.error}
              onReload={async () => {
                try {
                  await startDesktop({ viewOnly: desktop.viewOnly });
                } catch {
                  // Errors are surfaced via the workspace store.
                }
              }}
              onStop={async () => {
                try {
                  await stopDesktop();
                } catch {
                  // Errors are surfaced via the workspace store.
                }
              }}
            />
          )}
          {activeTab === "python" && (
            <PythonPanel
              language={pythonLanguage}
              onLanguageChange={setPythonLanguage}
              code={pythonCode}
              onCodeChange={setPythonCode}
              onRun={(code, timeoutSeconds, language) =>
                runPython(code, timeoutSeconds, language)
              }
              lastResult={python.lastResult}
              status={python.status}
              error={python.error}
            />
          )}
          {activeTab === "trace" && (
            <RunTracePanel events={trace.events} onClear={trace.clear} />
          )}
        </div>
      }
    />
  );
}

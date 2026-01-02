"use client";

import { ChatKitPanel } from "@/components/ChatKitPanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PythonPanel } from "@/components/PythonPanel";
import { RunTracePanel } from "@/components/RunTracePanel";
import { Toolbar } from "@/components/Toolbar";
import { VncPanel } from "@/components/VncPanel";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { useSandboxActions } from "@/hooks/useSandboxActions";
import { useWorkspaceStore } from "@/hooks/useWorkspaceStore";

export function WorkspaceShell() {
  const activeTab = useWorkspaceStore((state) => state.activeTab);
  const setActiveTab = useWorkspaceStore((state) => state.setActiveTab);
  const desktop = useWorkspaceStore((state) => state.desktop);
  const python = useWorkspaceStore((state) => state.python);
  const pythonCode = useWorkspaceStore((state) => state.python.code);
  const setPythonCode = useWorkspaceStore((state) => state.setPythonCode);
  const trace = useWorkspaceStore((state) => state.trace);
  const { startDesktop, stopDesktop, runPython } = useSandboxActions();

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
              code={pythonCode}
              onCodeChange={setPythonCode}
              onRun={runPython}
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

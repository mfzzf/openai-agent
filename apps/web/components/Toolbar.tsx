import type { WorkspaceTab } from "@/hooks/useWorkspaceStore";

const TAB_LABELS: Record<WorkspaceTab, string> = {
  desktop: "Desktop",
  python: "Python",
  trace: "Trace",
};

export function Toolbar(props: {
  activeTab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  desktopStatus: string;
  pythonStatus: string;
  desktopTimeLeft?: string | null;
  onExtendDesktop?: () => void;
  extendDesktopDisabled?: boolean;
}): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <div className="tabs">
        {(Object.keys(TAB_LABELS) as WorkspaceTab[]).map((tab) => (
          <button
            key={tab}
            className={`tab-button ${props.activeTab === tab ? "active" : ""}`}
            onClick={() => props.onTabChange(tab)}
            type="button"
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
        <span className="pill">Desktop: {props.desktopStatus}</span>
        {props.desktopTimeLeft ? (
          <span className="pill">Time left: {props.desktopTimeLeft}</span>
        ) : null}
        <span className="pill">Python: {props.pythonStatus}</span>
        {props.onExtendDesktop ? (
          <button
            className="button"
            type="button"
            onClick={props.onExtendDesktop}
            disabled={props.extendDesktopDisabled}
          >
            Extend +30m
          </button>
        ) : null}
      </div>
    </div>
  );
}

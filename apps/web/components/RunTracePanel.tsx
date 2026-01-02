import type { WorkspaceState } from "@/hooks/useWorkspaceStore";

export function RunTracePanel(props: {
  events: WorkspaceState["trace"]["events"];
  onClear: () => void;
}): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span className="panel-title">Trace events</span>
        <button className="button" type="button" onClick={props.onClear}>
          Clear
        </button>
      </div>
      <div className="panel-scroll" style={{ minHeight: 200 }}>
        {props.events.length === 0 ? (
          <div className="notice">No events yet. Client tools will appear here.</div>
        ) : (
          props.events.map((event) => (
            <div key={`${event.ts}-${event.title}`} className="trace-item">
              <div style={{ fontWeight: 600 }}>{event.title}</div>
              <div className="trace-meta">
                {new Date(event.ts).toLocaleTimeString()} · {event.type}
              </div>
              {event.detail != null && (
                <pre style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(event.detail, null, 2)}
                </pre>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

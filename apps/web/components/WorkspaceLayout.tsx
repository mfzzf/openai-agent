import type { ReactNode } from "react";

export function WorkspaceLayout(props: {
  left: ReactNode;
  right: ReactNode;
}): JSX.Element {
  return (
    <div className="workspace-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">ChatKit Session</div>
            <div className="panel-subtitle">Workflow-powered agent conversation</div>
          </div>
          <span className="pill">Live</span>
        </div>
        <div className="panel-body chatkit-shell">{props.left}</div>
      </section>
      <section className="panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">Workspace</div>
            <div className="panel-subtitle">Desktop, Python, and run trace</div>
          </div>
          <span className="pill">E2B</span>
        </div>
        <div className="panel-body">{props.right}</div>
      </section>
    </div>
  );
}

export function VncPanel(props: {
  streamUrl: string | null;
  viewOnly: boolean;
  error?: string;
  onReload: () => Promise<void>;
  onStop: () => Promise<void>;
}): JSX.Element {
  const handleReload = () => {
    void props.onReload();
  };

  const handleStop = () => {
    void props.onStop();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        <button className="button primary" type="button" onClick={handleReload}>
          {props.streamUrl ? "Restart Stream" : "Start Desktop"}
        </button>
        <button className="button ghost" type="button" onClick={handleStop}>
          Stop Stream
        </button>
        {props.streamUrl && (
          <a className="button" href={props.streamUrl} target="_blank" rel="noreferrer">
            Open in new tab
          </a>
        )}
      </div>
      {props.error && <div className="notice">{props.error}</div>}
      {!props.streamUrl ? (
        <div className="notice">
          No desktop stream yet. Ask the agent to start a desktop sandbox or use
          the button above.
        </div>
      ) : (
        <iframe
          className="vnc-frame"
          src={props.streamUrl}
          sandbox="allow-scripts allow-forms allow-same-origin"
          referrerPolicy="no-referrer"
          title="E2B Desktop"
        />
      )}
    </div>
  );
}

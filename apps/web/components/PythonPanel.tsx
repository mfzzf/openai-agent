"use client";

import { useState, type ReactNode } from "react";
import type { CodeLanguage, PythonRunResult } from "@/lib/types/sandbox";

export function PythonPanel(props: {
  language: CodeLanguage;
  onLanguageChange: (language: CodeLanguage) => void;
  code: string;
  onCodeChange: (code: string) => void;
  onRun: (
    code: string,
    timeoutSeconds: number | undefined,
    language: CodeLanguage
  ) => Promise<PythonRunResult>;
  lastResult?: PythonRunResult;
  status: "idle" | "ready" | "running" | "error";
  error?: string;
}): JSX.Element {
  const [timeout, setTimeoutValue] = useState("60");

  const handleRun = async () => {
    const timeoutSeconds = Number(timeout);
    try {
      await props.onRun(
        props.code,
        Number.isFinite(timeoutSeconds) ? timeoutSeconds : undefined,
        props.language
      );
    } catch {
      // Errors are surfaced via the workspace store.
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
        <button
          className="button primary"
          type="button"
          onClick={handleRun}
          disabled={props.status === "running"}
        >
          {props.status === "running" ? "Running..." : "Run Code"}
        </button>
        <label style={{ fontSize: 13, color: "var(--muted)" }}>
          Language
          <select
            value={props.language}
            onChange={(event) => props.onLanguageChange(event.target.value as CodeLanguage)}
            style={{
              marginLeft: 8,
              borderRadius: 8,
              border: "1px solid var(--border)",
              padding: "4px 6px",
            }}
            disabled={props.status === "running"}
          >
            <option value="python">python</option>
            <option value="go">go</option>
            <option value="js">js</option>
          </select>
        </label>
        <label style={{ fontSize: 13, color: "var(--muted)" }}>
          Timeout (s)
          <input
            value={timeout}
            onChange={(event) => setTimeoutValue(event.target.value)}
            style={{
              marginLeft: 8,
              width: 80,
              borderRadius: 8,
              border: "1px solid var(--border)",
              padding: "4px 6px",
            }}
          />
        </label>
        <span className="pill">Status: {props.status}</span>
      </div>
      <textarea
        className="code-input"
        value={props.code}
        onChange={(event) => props.onCodeChange(event.target.value)}
      />
      {props.error && <div className="notice">{props.error}</div>}
      {props.lastResult && (
        <div className="panel-scroll" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <OutputBlock label="Stdout">
            <pre>{props.lastResult.stdout.join("") || "(empty)"}</pre>
          </OutputBlock>
          <OutputBlock label="Stderr">
            <pre>{props.lastResult.stderr.join("") || "(empty)"}</pre>
          </OutputBlock>
          {props.lastResult.error && (
            <OutputBlock label="Error">
              <pre>
                {props.lastResult.error.name}: {props.lastResult.error.value}
                {"\n"}
                {props.lastResult.error.traceback.join("\n")}
              </pre>
            </OutputBlock>
          )}
          {props.lastResult.results.map((result, index) => (
            <ResultRenderer key={`${result.mime}-${index}`} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}

function OutputBlock(props: { label: string; children: ReactNode }) {
  return (
    <div className="output-block">
      <div className="output-title">{props.label}</div>
      {props.children}
    </div>
  );
}

function ResultRenderer(props: {
  result: PythonRunResult["results"][number];
}): JSX.Element {
  const { mime, data } = props.result;

  if (mime === "image/png") {
    return (
      <OutputBlock label="Result (image/png)">
        <img src={`data:image/png;base64,${data}`} alt="Code output" />
      </OutputBlock>
    );
  }

  if (mime === "image/jpeg") {
    return (
      <OutputBlock label="Result (image/jpeg)">
        <img src={`data:image/jpeg;base64,${data}`} alt="Code output" />
      </OutputBlock>
    );
  }

  if (mime === "text/html") {
    return (
      <OutputBlock label="Result (text/html)">
        <iframe
          title="Code HTML output"
          style={{ border: "none", width: "100%", minHeight: 240 }}
          srcDoc={data}
        />
      </OutputBlock>
    );
  }

  if (mime === "image/svg+xml") {
    return (
      <OutputBlock label="Result (image/svg+xml)">
        <img
          src={`data:image/svg+xml;utf8,${encodeURIComponent(data)}`}
          alt="Code output"
        />
      </OutputBlock>
    );
  }

  if (mime === "application/pdf") {
    return (
      <OutputBlock label="Result (application/pdf)">
        <iframe
          title="Code PDF output"
          style={{ border: "none", width: "100%", minHeight: 360 }}
          src={`data:application/pdf;base64,${data}`}
        />
      </OutputBlock>
    );
  }

  return (
    <OutputBlock label={`Result (${mime})`}>
      <pre>{data}</pre>
    </OutputBlock>
  );
}

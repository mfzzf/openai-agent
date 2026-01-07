export type DesktopSandboxSession = {
  sandboxId: string;
  streamUrl?: string;
  authKey?: string;
  viewOnly: boolean;
  createdAt: number;
  lastActiveAt: number;
  timeoutSeconds?: number;
  expiresAt?: number;
};

export type PythonSandboxSession = {
  sandboxId: string;
  createdAt: number;
  lastActiveAt: number;
};

export type CodeLanguage = "python" | "go" | "js" | "rust";

export type PythonRunRequest = {
  threadId: string;
  code: string;
  language?: CodeLanguage;
  timeoutSeconds?: number;
  envs?: Record<string, string>;
};

export type PythonRunResult = {
  executionId: string;
  stdout: string[];
  stderr: string[];
  results: Array<{
    mime: string;
    data: string;
    isMainResult?: boolean;
  }>;
  error?: {
    name: string;
    value: string;
    traceback: string[];
  };
};

import { randomUUID } from "crypto";
import { Sandbox } from "@e2b/code-interpreter";
import { getConfig } from "@/lib/config";
import {
  acquireLock,
  deleteKey,
  getJson,
  releaseLock,
  setJson,
} from "@/lib/store/redis";
import type {
  PythonRunRequest,
  PythonRunResult,
  PythonSandboxSession,
} from "@/lib/types/sandbox";

const PYTHON_TTL_SECONDS = 30 * 60;
const PYTHON_KEY_PREFIX = "python:";
const PYTHON_LOCK_PREFIX = "lock:python:";

function getPythonKey(threadId: string) {
  return `${PYTHON_KEY_PREFIX}${threadId}`;
}

function getPythonLockKey(threadId: string) {
  return `${PYTHON_LOCK_PREFIX}${threadId}`;
}

async function connectPython(sandboxId: string) {
  const config = getConfig();
  return Sandbox.connect(sandboxId, { apiKey: config.e2bApiKey });
}

export async function pythonCreate(params: {
  threadId: string;
}): Promise<PythonSandboxSession> {
  const key = getPythonKey(params.threadId);
  const now = Date.now();
  const existing = await getJson<PythonSandboxSession>(key);
  if (existing) {
    const session = { ...existing, lastActiveAt: now };
    await setJson(key, session, PYTHON_TTL_SECONDS);
    return session;
  }

  const lockKey = getPythonLockKey(params.threadId);
  const token = await acquireLock(lockKey, 15);
  if (!token) {
    const retry = await getJson<PythonSandboxSession>(key);
    if (retry) {
      return retry;
    }
    throw new Error("Python sandbox is busy. Try again.");
  }

  try {
    const config = getConfig();
    const sandbox = await Sandbox.create({ apiKey: config.e2bApiKey });
    const session: PythonSandboxSession = {
      sandboxId: sandbox.sandboxId,
      createdAt: now,
      lastActiveAt: now,
    };
    await setJson(key, session, PYTHON_TTL_SECONDS);
    return session;
  } finally {
    await releaseLock(lockKey, token);
  }
}

export async function pythonRun(params: PythonRunRequest): Promise<PythonRunResult> {
  const session = await pythonCreate({ threadId: params.threadId });
  const sandbox = await connectPython(session.sandboxId);

  const execution = await sandbox.runCode(params.code, {
    envs: params.envs,
    timeoutMs: params.timeoutSeconds ? params.timeoutSeconds * 1000 : undefined,
  });

  const results: PythonRunResult["results"] = [];

  (execution.results ?? []).forEach((result) => {
    const pushResult = (mime: string, data?: string) => {
      if (data === undefined) {
        return;
      }
      results.push({
        mime,
        data,
        isMainResult: result.isMainResult,
      });
    };

    pushResult("text/plain", result.text);
    pushResult("text/html", result.html);
    pushResult("text/markdown", result.markdown);
    pushResult("image/svg+xml", result.svg);
    pushResult("image/png", result.png);
    pushResult("image/jpeg", result.jpeg);
    pushResult("application/pdf", result.pdf);
    pushResult("text/latex", result.latex);
    pushResult("application/json", result.json);
    pushResult("application/javascript", result.javascript);

    if (!result.json && result.data) {
      pushResult("application/json", JSON.stringify(result.data));
    }

    if (result.chart) {
      pushResult("application/json", JSON.stringify(result.chart));
    }
  });

  const executionId = execution.executionCount
    ? String(execution.executionCount)
    : randomUUID();

  const runResult: PythonRunResult = {
    executionId,
    stdout: execution.logs?.stdout ?? [],
    stderr: execution.logs?.stderr ?? [],
    results,
    error: execution.error
      ? {
          name: execution.error.name,
          value: execution.error.value,
          traceback: Array.isArray(execution.error.traceback)
            ? execution.error.traceback
            : execution.error.traceback
              ? [execution.error.traceback]
              : [],
        }
      : undefined,
  };

  const updatedSession: PythonSandboxSession = {
    ...session,
    lastActiveAt: Date.now(),
  };

  await setJson(getPythonKey(params.threadId), updatedSession, PYTHON_TTL_SECONDS);
  return runResult;
}

export async function pythonKill(params: {
  threadId: string;
}): Promise<{ killed: boolean }> {
  const key = getPythonKey(params.threadId);
  const session = await getJson<PythonSandboxSession>(key);
  if (!session) {
    return { killed: false };
  }

  const config = getConfig();
  await Sandbox.kill(session.sandboxId, { apiKey: config.e2bApiKey });
  await deleteKey(key);
  return { killed: true };
}

export async function pythonGetStatus(params: {
  threadId: string;
}): Promise<PythonSandboxSession | null> {
  const key = getPythonKey(params.threadId);
  return await getJson<PythonSandboxSession>(key);
}

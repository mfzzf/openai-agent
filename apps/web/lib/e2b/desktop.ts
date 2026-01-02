import { Sandbox } from "@e2b/desktop";
import { getConfig } from "@/lib/config";
import {
  acquireLock,
  deleteKey,
  getJson,
  releaseLock,
  setJson,
} from "@/lib/store/redis";
import type { DesktopSandboxSession } from "@/lib/types/sandbox";

const DESKTOP_TTL_SECONDS = 30 * 60;
const DESKTOP_KEY_PREFIX = "desktop:";
const DESKTOP_LOCK_PREFIX = "lock:desktop:";

function getDesktopKey(threadId: string) {
  return `${DESKTOP_KEY_PREFIX}${threadId}`;
}

function getDesktopLockKey(threadId: string) {
  return `${DESKTOP_LOCK_PREFIX}${threadId}`;
}

async function connectDesktop(sandboxId: string) {
  const config = getConfig();
  return Sandbox.connect(sandboxId, { apiKey: config.e2bApiKey });
}

export async function desktopStart(params: {
  threadId: string;
  requireAuth: boolean;
  viewOnly: boolean;
}): Promise<DesktopSandboxSession> {
  const { threadId, requireAuth, viewOnly } = params;
  const key = getDesktopKey(threadId);
  const now = Date.now();
  const existing = await getJson<DesktopSandboxSession>(key);

  if (existing) {
    let streamUrl = existing.streamUrl;
    let authKey = existing.authKey;

    if (!streamUrl) {
      const desktop = await connectDesktop(existing.sandboxId);
      await desktop.stream.start({ requireAuth });
      authKey = requireAuth ? desktop.stream.getAuthKey() : undefined;
      streamUrl = desktop.stream.getUrl({ authKey, viewOnly });
    } else if (existing.viewOnly !== viewOnly) {
      const desktop = await connectDesktop(existing.sandboxId);
      streamUrl = desktop.stream.getUrl({ authKey, viewOnly });
    }

    const session: DesktopSandboxSession = {
      ...existing,
      streamUrl,
      authKey,
      viewOnly,
      lastActiveAt: now,
    };

    await setJson(key, session, DESKTOP_TTL_SECONDS);
    return session;
  }

  const lockKey = getDesktopLockKey(threadId);
  const token = await acquireLock(lockKey, 15);
  if (!token) {
    const retry = await getJson<DesktopSandboxSession>(key);
    if (retry) {
      return retry;
    }
    throw new Error("Desktop sandbox is busy. Try again.");
  }

  try {
    const config = getConfig();
    const desktop = await Sandbox.create({ apiKey: config.e2bApiKey });
    await desktop.stream.start({ requireAuth });
    const authKey = requireAuth ? desktop.stream.getAuthKey() : undefined;
    const streamUrl = desktop.stream.getUrl({ authKey, viewOnly });
    const session: DesktopSandboxSession = {
      sandboxId: desktop.sandboxId,
      streamUrl,
      authKey,
      viewOnly,
      createdAt: now,
      lastActiveAt: now,
    };

    await setJson(key, session, DESKTOP_TTL_SECONDS);
    return session;
  } finally {
    await releaseLock(lockKey, token);
  }
}

export async function desktopStop(params: {
  threadId: string;
}): Promise<{ stopped: boolean }> {
  const key = getDesktopKey(params.threadId);
  const session = await getJson<DesktopSandboxSession>(key);
  if (!session) {
    return { stopped: false };
  }

  const desktop = await connectDesktop(session.sandboxId);
  try {
    await desktop.stream.stop();
  } catch (error) {
    console.warn("Desktop stream stop warning", error);
  }

  const updated: DesktopSandboxSession = {
    ...session,
    streamUrl: undefined,
    authKey: undefined,
    lastActiveAt: Date.now(),
  };

  await setJson(key, updated, DESKTOP_TTL_SECONDS);
  return { stopped: true };
}

export async function desktopGetStatus(params: {
  threadId: string;
}): Promise<DesktopSandboxSession | null> {
  const key = getDesktopKey(params.threadId);
  return await getJson<DesktopSandboxSession>(key);
}

export async function desktopKill(params: {
  threadId: string;
}): Promise<{ killed: boolean }> {
  const key = getDesktopKey(params.threadId);
  const session = await getJson<DesktopSandboxSession>(key);
  if (!session) {
    return { killed: false };
  }

  const config = getConfig();
  await Sandbox.kill(session.sandboxId, { apiKey: config.e2bApiKey });
  await deleteKey(key);
  return { killed: true };
}

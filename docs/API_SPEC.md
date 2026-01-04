# API 规范（ChatKit Session + E2B Sandboxes）

本文档给出后端 API 的请求/响应结构与错误约定，便于前后端联调与工具契约落地。

## 1. 通用错误结构

```ts
export type ApiError = {
  ok: false;
  error: {
    code: string;
    message: string;
  };
};
```

## 2. ChatKit Session

### POST `/api/create-session`

**Request**
```ts
export type CreateSessionRequest = {
  userId?: string;
};
```

**Response**
```ts
export type CreateSessionResponse = {
  clientSecret: string;
  expiresAt: number; // unix seconds
  workflowId: string;
};
```

**Notes**
- 后端优先使用 `userId`，否则以 `ck_uid` cookie 作为匿名用户标识。
- `clientSecret` 通常 10 分钟过期，需要前端刷新。

## 3. Desktop Sandbox

### POST `/api/sandbox/desktop/start`

**Request**
```ts
type DesktopStartApiRequest = {
  threadId: string;
  requireAuth?: boolean; // default true
  viewOnly?: boolean;    // default false
};
```

**Response**
```ts
type DesktopStartApiResponse = {
  ok: true;
  session: {
    sandboxId: string;
    streamUrl?: string;
    authKey?: string;
    viewOnly: boolean;
    createdAt: number;
    lastActiveAt: number;
  };
};
```

### POST `/api/sandbox/desktop/stop`

**Request**
```ts
type DesktopStopApiRequest = { threadId: string };
```

**Response**
```ts
type DesktopStopApiResponse = { ok: true; stopped: boolean };
```

### GET `/api/sandbox/desktop/status?threadId=...`

**Response**
```ts
type DesktopStatusApiResponse =
  | { ok: true; session: DesktopSandboxSession | null }
  | ApiError;
```

## 4. Python Sandbox

### POST `/api/sandbox/python/create`

**Request**
```ts
type PythonCreateApiRequest = { threadId: string };
```

**Response**
```ts
type PythonCreateApiResponse = { ok: true; session: PythonSandboxSession };
```

### POST `/api/sandbox/python/run`

**Request**
```ts
type PythonRunApiRequest = {
  threadId: string;
  code: string;
  timeoutSeconds?: number;
  envs?: Record<string, string>;
};
```

**Response**
```ts
type PythonRunApiResponse = { ok: true; result: PythonRunResult };
```

### POST `/api/sandbox/python/kill`

**Request**
```ts
type PythonKillApiRequest = { threadId: string };
```

**Response**
```ts
type PythonKillApiResponse = { ok: true; killed: boolean };
```

## 5. Computer Use（Phase 2，可选）

### POST `/api/computer-use/run`

**Request**
```ts
type ComputerUseRunApiRequest = {
  threadId: string;
  goal: string;
  maxSteps?: number;        // default 30
  model?: string;           // default "gpt-5"
};
```

**Response**
```ts
type ComputerUseRunApiResponse =
  | {
      ok: true;
      runId: string;
      status: "completed";
      streamUrl: string;
      summary: string;
      steps: Array<{
        i: number;
        action: { type: string; args: any };
        observation?: { screenshotStoredAt?: string };
        ts: number;
      }>;
    }
  | ApiError;
```

---

## 6. 工具协议（与 Agent Builder 一致）

> 这些工具名称应与 Agent Builder 中的 client tools 保持一致。

1. `sandbox.desktop.start`
   - args: `{ threadId?: string, viewOnly?: boolean, requireAuth?: boolean }`
   - return: `{ ok: true, streamUrl: string, viewOnly: boolean }`

2. `sandbox.desktop.stop`
   - args: `{ threadId?: string }`
   - return: `{ ok: true }`

3. `sandbox.python.run`
   - args: `{ threadId?: string, code: string, timeoutSeconds?: number }`
   - return: `{ ok: true, result: PythonRunResult }`

4. `ui.openTab`
   - args: `{ tab: "desktop"|"python"|"trace" }`
   - return: `{ ok: true }`

5. `ui.notify`
   - args: `{ level:"info"|"warn"|"error", message:string }`
   - return: `{ ok: true }`

6. `sandbox.desktop.click`
   - args: `{ threadId?: string, x: number, y: number, button?: "left"|"right"|"middle", double?: boolean }`
   - return: `{ ok: true }`

7. `sandbox.desktop.type`
   - args: `{ threadId?: string, text: string, chunkSize?: number, delayInMs?: number }`
   - return: `{ ok: true }`

8. `sandbox.desktop.press`
   - args: `{ threadId?: string, keys: string[] }`
   - return: `{ ok: true }`

9. `sandbox.desktop.wait`
   - args: `{ threadId?: string, ms: number }`
   - return: `{ ok: true }`

10. `sandbox.desktop.scroll`
   - args: `{ threadId?: string, direction?: "up"|"down", amount?: number }`
   - return: `{ ok: true }`

11. `sandbox.desktop.moveMouse`
   - args: `{ threadId?: string, x: number, y: number }`
   - return: `{ ok: true }`

12. `sandbox.desktop.drag`
   - args: `{ threadId?: string, fromX: number, fromY: number, toX: number, toY: number }`
   - return: `{ ok: true }`

13. `sandbox.desktop.screenshot`
   - args: `{ threadId?: string, includeCursor?: boolean, includeScreenSize?: boolean }`
   - return: `{ ok: true, mime: "image/png", imageBase64: string, screenSize?: { width:number, height:number }, cursorPosition?: { x:number, y:number } }`

> 坐标约定：所有 `x/y` 都是截图的像素坐标，左上角为原点 `(0,0)`。

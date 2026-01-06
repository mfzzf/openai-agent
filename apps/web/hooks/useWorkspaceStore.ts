import { create } from "zustand";
import type { CodeLanguage, PythonRunResult } from "@/lib/types/sandbox";

export type WorkspaceTab = "desktop" | "python" | "trace";

type TraceEvent = {
  ts: number;
  type: "info" | "tool" | "error";
  title: string;
  detail?: unknown;
};

export type ToolEventSource = "chatkit" | "manual" | "system";

export type ToolEvent = {
  tool: string;
  params?: Record<string, unknown>;
  result?: unknown;
  status: "success" | "error";
  source?: ToolEventSource;
  callId?: string;
};

const DEFAULT_PYTHON_CODE = "import math\n\n[(n, math.sqrt(n)) for n in range(1, 6)]";

export type WorkspaceState = {
  threadId: string | null;
  setThreadId: (threadId: string | null) => void;
  sandboxThreadId: string | null;
  setSandboxThreadId: (threadId: string | null) => void;
  activeTab: WorkspaceTab;
  setActiveTab: (tab: WorkspaceTab) => void;
  desktop: {
    streamUrl: string | null;
    viewOnly: boolean;
    status: "idle" | "starting" | "ready" | "error";
    error?: string;
    timeoutSeconds?: number;
    expiresAt?: number;
  };
  setDesktop: (patch: Partial<WorkspaceState["desktop"]>) => void;
  python: {
    language: CodeLanguage;
    code: string;
    status: "idle" | "ready" | "running" | "error";
    lastResult?: PythonRunResult;
    error?: string;
  };
  setPython: (patch: Partial<WorkspaceState["python"]>) => void;
  setPythonCode: (code: string) => void;
  setPythonLanguage: (language: CodeLanguage) => void;
  trace: {
    events: TraceEvent[];
    addEvent: (event: TraceEvent) => void;
    clear: () => void;
  };
  toolEventEmitter: ((event: ToolEvent) => Promise<void> | void) | null;
  setToolEventEmitter: (
    emitter: WorkspaceState["toolEventEmitter"] | null
  ) => void;
  emitToolEvent: (event: ToolEvent) => Promise<void>;
  addNotice: (level: "info" | "warn" | "error", message: string) => void;
};

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  threadId: null,
  setThreadId: (threadId) => set({ threadId }),
  sandboxThreadId: null,
  setSandboxThreadId: (sandboxThreadId) => set({ sandboxThreadId }),
  activeTab: "desktop",
  setActiveTab: (tab) => set({ activeTab: tab }),
  desktop: {
    streamUrl: null,
    viewOnly: false,
    status: "idle",
    timeoutSeconds: undefined,
    expiresAt: undefined,
  },
  setDesktop: (patch) =>
    set((state) => ({
      desktop: {
        ...state.desktop,
        ...patch,
      },
    })),
  python: {
    language: "python",
    code: DEFAULT_PYTHON_CODE,
    status: "idle",
  },
  setPython: (patch) =>
    set((state) => ({
      python: {
        ...state.python,
        ...patch,
      },
    })),
  setPythonCode: (code) =>
    set((state) => ({
      python: {
        ...state.python,
        code,
      },
    })),
  setPythonLanguage: (language) =>
    set((state) => ({
      python: {
        ...state.python,
        language,
      },
    })),
  trace: {
    events: [],
    addEvent: (event) =>
      set((state) => ({
        trace: {
          ...state.trace,
          events: [event, ...state.trace.events].slice(0, 200),
        },
      })),
    clear: () =>
      set((state) => ({
        trace: {
          ...state.trace,
          events: [],
        },
      })),
  },
  toolEventEmitter: null,
  setToolEventEmitter: (emitter) => set({ toolEventEmitter: emitter ?? null }),
  emitToolEvent: async (event) => {
    const emitter = get().toolEventEmitter;
    if (!emitter) {
      return;
    }
    try {
      await emitter(event);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to emit tool event";
      get().trace.addEvent({
        ts: Date.now(),
        type: "error",
        title: "tool.emit_error",
        detail: { message, tool: event.tool },
      });
    }
  },
  addNotice: (level, message) => {
    const type = level === "error" ? "error" : "info";
    get().trace.addEvent({
      ts: Date.now(),
      type,
      title: `notice:${level}`,
      detail: { message },
    });
  },
}));

import { z } from "zod";

export const desktopStartSchema = z.object({
  threadId: z.string().min(1),
  requireAuth: z.boolean().optional(),
  viewOnly: z.boolean().optional(),
});

export const desktopStopSchema = z.object({
  threadId: z.string().min(1),
});

export const desktopKillSchema = z.object({
  threadId: z.string().min(1),
});

export const desktopStatusSchema = z.object({
  threadId: z.string().min(1),
});

export const desktopTimeoutSchema = z.object({
  threadId: z.string().min(1),
  timeoutSeconds: z.preprocess(
    (value) => (value === null ? undefined : value),
    z.number().int().positive()
  ),
});

export const desktopActionSchema = z.discriminatedUnion("action", [
  z.object({
    threadId: z.string().min(1),
    action: z.literal("click"),
    x: z.number().int().nonnegative(),
    y: z.number().int().nonnegative(),
    button: z.enum(["left", "right", "middle"]).optional(),
    double: z.boolean().optional(),
  }),
  z.object({
    threadId: z.string().min(1),
    action: z.literal("type"),
    text: z.string().min(1),
    chunkSize: z.number().int().positive().optional(),
    delayInMs: z.number().int().nonnegative().optional(),
  }),
  z.object({
    threadId: z.string().min(1),
    action: z.literal("press"),
    keys: z.array(z.string().min(1)).min(1),
  }),
  z.object({
    threadId: z.string().min(1),
    action: z.literal("wait"),
    ms: z.number().int().nonnegative(),
  }),
  z.object({
    threadId: z.string().min(1),
    action: z.literal("scroll"),
    direction: z.enum(["up", "down"]).optional(),
    amount: z.number().int().positive().optional(),
  }),
  z.object({
    threadId: z.string().min(1),
    action: z.literal("moveMouse"),
    x: z.number().int().nonnegative(),
    y: z.number().int().nonnegative(),
  }),
  z.object({
    threadId: z.string().min(1),
    action: z.literal("drag"),
    fromX: z.number().int().nonnegative(),
    fromY: z.number().int().nonnegative(),
    toX: z.number().int().nonnegative(),
    toY: z.number().int().nonnegative(),
  }),
]);

export const desktopScreenshotSchema = z.object({
  threadId: z.string().min(1),
  includeCursor: z.boolean().optional(),
  includeScreenSize: z.boolean().optional(),
});

export const pythonCreateSchema = z.object({
  threadId: z.string().min(1),
});

export const pythonRunSchema = z.object({
  threadId: z.string().min(1),
  code: z.string().min(1),
  language: z.enum(["python", "go", "js"]).optional(),
  timeoutSeconds: z.preprocess(
    (value) => (value === null ? undefined : value),
    z.number().int().positive().optional()
  ),
  envs: z.preprocess(
    (value) => (value === null ? undefined : value),
    z.record(z.string()).optional()
  ),
});

export const pythonKillSchema = z.object({
  threadId: z.string().min(1),
});

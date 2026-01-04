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

export const pythonCreateSchema = z.object({
  threadId: z.string().min(1),
});

export const pythonRunSchema = z.object({
  threadId: z.string().min(1),
  code: z.string().min(1),
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

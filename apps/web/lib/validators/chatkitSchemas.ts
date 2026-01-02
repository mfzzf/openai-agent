import { z } from "zod";

export const createSessionSchema = z.object({
  userId: z.string().min(1).optional(),
});

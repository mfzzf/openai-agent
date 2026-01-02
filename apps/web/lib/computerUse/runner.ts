import type { ComputerUseAction } from "@/lib/types/computerUse";

export async function runComputerUse(params: {
  threadId: string;
  goal: string;
  maxSteps: number;
  model: string;
}): Promise<{
  summary: string;
  steps: Array<{
    i: number;
    action: ComputerUseAction;
    ts: number;
  }>;
}> {
  void params;
  throw new Error("Computer Use runner is not implemented yet.");
}

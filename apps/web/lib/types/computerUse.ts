export type ComputerUseAction =
  | { type: "click"; x: number; y: number; button?: "left" | "right" }
  | { type: "type"; text: string }
  | { type: "press"; keys: string[] }
  | { type: "wait"; ms: number };

export type ComputerUseStep = {
  i: number;
  action: ComputerUseAction;
  ts: number;
  observation?: { screenshotStoredAt?: string };
};

export type ComputerUseRunResult = {
  runId: string;
  status: "completed";
  streamUrl: string;
  summary: string;
  steps: ComputerUseStep[];
};

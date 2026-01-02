import { NextRequest, NextResponse } from "next/server";
import { pythonKill } from "@/lib/e2b/python";
import { pythonKillSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = pythonKillSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const result = await pythonKill({ threadId: parsed.data.threadId });
    return NextResponse.json({ ok: true, killed: result.killed });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to kill sandbox";
    return NextResponse.json(
      { ok: false, error: { code: "python_kill_failed", message } },
      { status: 500 }
    );
  }
}

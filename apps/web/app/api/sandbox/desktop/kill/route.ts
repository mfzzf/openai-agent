import { NextRequest, NextResponse } from "next/server";
import { desktopKill } from "@/lib/e2b/desktop";
import { desktopKillSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = desktopKillSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const result = await desktopKill({ threadId: parsed.data.threadId });
    return NextResponse.json({ ok: true, killed: result.killed });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to kill desktop";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_kill_failed", message } },
      { status: 500 }
    );
  }
}

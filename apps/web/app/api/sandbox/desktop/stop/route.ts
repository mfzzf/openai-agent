import { NextRequest, NextResponse } from "next/server";
import { desktopStop } from "@/lib/e2b/desktop";
import { desktopStopSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = desktopStopSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const result = await desktopStop({ threadId: parsed.data.threadId });
    return NextResponse.json({ ok: true, stopped: result.stopped });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to stop desktop";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_stop_failed", message } },
      { status: 500 }
    );
  }
}

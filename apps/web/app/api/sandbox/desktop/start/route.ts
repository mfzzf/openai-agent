import { NextRequest, NextResponse } from "next/server";
import { desktopStart } from "@/lib/e2b/desktop";
import { desktopStartSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = desktopStartSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const session = await desktopStart({
      threadId: parsed.data.threadId,
      requireAuth: parsed.data.requireAuth ?? true,
      viewOnly: parsed.data.viewOnly ?? false,
    });

    return NextResponse.json({ ok: true, session });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to start desktop";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_start_failed", message } },
      { status: 500 }
    );
  }
}

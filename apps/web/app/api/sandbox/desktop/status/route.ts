import { NextRequest, NextResponse } from "next/server";
import { desktopGetStatus } from "@/lib/e2b/desktop";
import { desktopStatusSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const threadId = req.nextUrl.searchParams.get("threadId") ?? "";
  const parsed = desktopStatusSchema.safeParse({ threadId });
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Missing threadId" } },
      { status: 400 }
    );
  }

  try {
    const session = await desktopGetStatus({ threadId: parsed.data.threadId });
    return NextResponse.json({ ok: true, session });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to get status";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_status_failed", message } },
      { status: 500 }
    );
  }
}

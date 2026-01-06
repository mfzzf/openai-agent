import { NextRequest, NextResponse } from "next/server";
import { desktopSetTimeout } from "@/lib/e2b/desktop";
import { desktopTimeoutSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = desktopTimeoutSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const session = await desktopSetTimeout(parsed.data);
    return NextResponse.json({ ok: true, session });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to update desktop timeout";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_timeout_failed", message } },
      { status: 500 }
    );
  }
}


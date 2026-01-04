import { NextRequest, NextResponse } from "next/server";
import { desktopAction } from "@/lib/e2b/desktop";
import { desktopActionSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = desktopActionSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const result = await desktopAction(parsed.data);
    return NextResponse.json({ ok: true, result });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to run desktop action";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_action_failed", message } },
      { status: 500 }
    );
  }
}


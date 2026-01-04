import { NextRequest, NextResponse } from "next/server";
import { desktopScreenshot } from "@/lib/e2b/desktop";
import { desktopScreenshotSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = desktopScreenshotSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const screenshot = await desktopScreenshot(parsed.data);
    return NextResponse.json({ ok: true, screenshot });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to take screenshot";
    return NextResponse.json(
      { ok: false, error: { code: "desktop_screenshot_failed", message } },
      { status: 500 }
    );
  }
}


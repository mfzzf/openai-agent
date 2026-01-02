import { NextRequest, NextResponse } from "next/server";
import { pythonRun } from "@/lib/e2b/python";
import { pythonRunSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = pythonRunSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const result = await pythonRun(parsed.data);
    return NextResponse.json({ ok: true, result });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to run code";
    return NextResponse.json(
      { ok: false, error: { code: "python_run_failed", message } },
      { status: 500 }
    );
  }
}

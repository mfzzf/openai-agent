import { NextRequest, NextResponse } from "next/server";
import { pythonCreate } from "@/lib/e2b/python";
import { pythonCreateSchema } from "@/lib/validators/sandboxSchemas";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = pythonCreateSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const session = await pythonCreate({ threadId: parsed.data.threadId });
    return NextResponse.json({ ok: true, session });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to create sandbox";
    return NextResponse.json(
      { ok: false, error: { code: "python_create_failed", message } },
      { status: 500 }
    );
  }
}

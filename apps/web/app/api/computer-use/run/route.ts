import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST() {
  return NextResponse.json(
    {
      ok: false,
      error: {
        code: "not_implemented",
        message: "Computer Use runner is not enabled in this build.",
      },
    },
    { status: 501 }
  );
}

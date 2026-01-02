import { randomUUID } from "crypto";
import { NextRequest, NextResponse } from "next/server";
import { createSessionSchema } from "@/lib/validators/chatkitSchemas";
import { getConfig } from "@/lib/config";
import { getOpenAIClient } from "@/lib/openai";
import type { CreateSessionResponse } from "@/lib/types/chatkit";

export const runtime = "nodejs";

const USER_COOKIE = "ck_uid";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

async function resolveUserId(req: NextRequest, bodyUserId?: string) {
  if (bodyUserId) {
    return bodyUserId;
  }

  const cookie = req.cookies.get(USER_COOKIE)?.value;
  if (cookie) {
    return cookie;
  }

  return randomUUID();
}

async function createChatKitSession(params: {
  userId: string;
  workflowId: string;
}) {
  const client = getOpenAIClient();
  const session = await client.beta.chatkit.sessions.create({
    user: params.userId,
    workflow: { id: params.workflowId },
  });
  return {
    clientSecret: session.client_secret,
    expiresAt: session.expires_at,
  };
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const parsed = createSessionSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: { code: "invalid_request", message: "Invalid payload" } },
      { status: 400 }
    );
  }

  try {
    const config = getConfig();
    if (!config.chatkitWorkflowId) {
      return NextResponse.json(
        {
          ok: false,
          error: {
            code: "missing_workflow",
            message: "ChatKit workflow ID is not configured.",
          },
        },
        { status: 500 }
      );
    }
    const userId = await resolveUserId(req, parsed.data.userId);
    const { clientSecret, expiresAt } = await createChatKitSession({
      userId,
      workflowId: config.chatkitWorkflowId,
    });

    const responseBody: CreateSessionResponse = {
      clientSecret,
      expiresAt,
      workflowId: config.chatkitWorkflowId,
    };

    const response = NextResponse.json(responseBody);
    if (!parsed.data.userId) {
      response.cookies.set(USER_COOKIE, userId, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: COOKIE_MAX_AGE,
        path: "/",
      });
    }

    return response;
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Failed to create session";
    return NextResponse.json(
      { ok: false, error: { code: "session_create_failed", message } },
      { status: 500 }
    );
  }
}

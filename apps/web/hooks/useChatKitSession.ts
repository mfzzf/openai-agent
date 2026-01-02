"use client";

import { useRef } from "react";
import type { CreateSessionResponse } from "@/lib/types/chatkit";

const REFRESH_WINDOW_MS = 60_000;

type SessionCache = {
  clientSecret: string | null;
  expiresAt: number | null;
};

export function useChatKitSession() {
  const cacheRef = useRef<SessionCache>({
    clientSecret: null,
    expiresAt: null,
  });

  const getClientSecret = async (currentClientSecret: string | null) => {
    const cache = cacheRef.current;
    const now = Date.now();

    if (
      cache.clientSecret &&
      cache.expiresAt &&
      cache.expiresAt * 1000 - now > REFRESH_WINDOW_MS
    ) {
      return cache.clientSecret;
    }

    if (
      currentClientSecret &&
      cache.expiresAt &&
      cache.clientSecret === currentClientSecret &&
      cache.expiresAt * 1000 - now > REFRESH_WINDOW_MS
    ) {
      return currentClientSecret;
    }

    const response = await fetch("/api/create-session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      throw new Error("Failed to create ChatKit session");
    }

    const data = (await response.json()) as CreateSessionResponse;
    cacheRef.current = {
      clientSecret: data.clientSecret,
      expiresAt: data.expiresAt,
    };
    return data.clientSecret;
  };

  return { getClientSecret };
}

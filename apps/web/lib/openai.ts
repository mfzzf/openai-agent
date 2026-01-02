import OpenAI from "openai";
import { getConfig } from "@/lib/config";

type OpenAIClient = OpenAI;

const globalForOpenAI = globalThis as unknown as { openai?: OpenAIClient };

export function getOpenAIClient(): OpenAIClient {
  if (!globalForOpenAI.openai) {
    const config = getConfig();
    globalForOpenAI.openai = new OpenAI({
      apiKey: config.openaiApiKey,
      baseURL: config.openaiBaseUrl,
    });
  }
  return globalForOpenAI.openai;
}

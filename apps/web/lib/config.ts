export type AppConfig = {
  openaiApiKey: string;
  openaiBaseUrl?: string;
  chatkitWorkflowId?: string;
  e2bApiKey: string;
  redisUrl: string;
  appUrl: string;
};

let cachedConfig: AppConfig | null = null;

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function optionalEnv(name: string): string | undefined {
  const value = process.env[name]?.trim();
  return value ? value : undefined;
}

export function getConfig(): AppConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  cachedConfig = {
    openaiApiKey: requireEnv("OPENAI_API_KEY"),
    openaiBaseUrl: optionalEnv("OPENAI_BASE_URL"),
    chatkitWorkflowId: optionalEnv("NEXT_PUBLIC_CHATKIT_WORKFLOW_ID"),
    e2bApiKey: requireEnv("E2B_API_KEY"),
    redisUrl: requireEnv("REDIS_URL"),
    appUrl: requireEnv("NEXT_PUBLIC_APP_URL"),
  };

  if (
    !cachedConfig.chatkitWorkflowId &&
    !optionalEnv("NEXT_PUBLIC_CHATKIT_API_URL")
  ) {
    throw new Error(
      "Missing ChatKit configuration: set NEXT_PUBLIC_CHATKIT_WORKFLOW_ID or NEXT_PUBLIC_CHATKIT_API_URL."
    );
  }

  return cachedConfig;
}

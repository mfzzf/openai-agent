import { randomUUID } from "crypto";
import { createClient } from "redis";
import { getConfig } from "@/lib/config";

export type RedisClient = ReturnType<typeof createClient>;

const globalForRedis = globalThis as unknown as { redis?: RedisClient };

export async function getRedisClient(): Promise<RedisClient> {
  if (!globalForRedis.redis) {
    const config = getConfig();
    globalForRedis.redis = createClient({ url: config.redisUrl });
    globalForRedis.redis.on("error", (error) => {
      console.error("Redis error", error);
    });
  }

  if (!globalForRedis.redis.isOpen) {
    await globalForRedis.redis.connect();
  }

  return globalForRedis.redis;
}

export async function getJson<T>(key: string): Promise<T | null> {
  const client = await getRedisClient();
  const value = await client.get(key);
  if (!value) {
    return null;
  }
  return JSON.parse(value) as T;
}

export async function setJson(
  key: string,
  value: unknown,
  ttlSeconds: number
): Promise<void> {
  const client = await getRedisClient();
  await client.set(key, JSON.stringify(value), { EX: ttlSeconds });
}

export async function deleteKey(key: string): Promise<void> {
  const client = await getRedisClient();
  await client.del(key);
}

export async function acquireLock(
  key: string,
  ttlSeconds: number
): Promise<string | null> {
  const client = await getRedisClient();
  const token = randomUUID();
  const result = await client.set(key, token, { NX: true, EX: ttlSeconds });
  return result === "OK" ? token : null;
}

export async function releaseLock(key: string, token: string): Promise<void> {
  const client = await getRedisClient();
  const value = await client.get(key);
  if (value === token) {
    await client.del(key);
  }
}

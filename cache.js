import { createClient } from "redis";
const redis = createClient({ url: process.env.REDIS_URL });
redis.on("error", (err) => console.error("Redis error:", err));
await redis.connect();

export async function cacheData(key, data) {
  await redis.set(key, JSON.stringify(data), { EX: 600 });
}

export async function getCachedData(key) {
  const raw = await redis.get(key);
  return raw ? JSON.parse(raw) : null;
}

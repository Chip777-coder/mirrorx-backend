import cron from "node-cron";
import axios from "axios";
import { cacheData } from "./cache.js";

export function startScheduler() {
  console.log("🕒 Auto Intelligence Scheduler started...");

  cron.schedule("*/10 * * * *", async () => {
    try {
      console.log("🔁 Fetching Solana/Jupiter intelligence...");
      const [gecko, birdeye] = await Promise.all([
        axios.get(`${process.env.COINGECKO_BASE_URL}/coins/markets`, {
          params: { vs_currency: "usd", category: "solana-ecosystem" },
        }),
        axios.get(`${process.env.BIRDEYE_BASE_URL}/public/tokenlist`),
      ]);
      const jupiter = await axios.get(`${process.env.JUPITER_API_URL}/v4/price?ids=SOL,USDC,USDT`);

      await cacheData("jupiter_intel", {
        updated: new Date(),
        solanaTokens: gecko.data.slice(0, 5),
        birdeyeTop: birdeye.data.tokens?.slice(0, 5) || [],
        jupiterPrices: jupiter.data.data,
      });
      console.log("✅ Crypto intelligence refreshed");
    } catch (err) {
      console.error("❌ Scheduler crypto update failed:", err.message);
    }
  });

  cron.schedule("*/30 * * * *", async () => {
    try {
      console.log("📈 Fetching Twitter social intel...");
      const response = await axios.get(`https://${process.env.RAPIDAPI_HOST}/likes`, {
        headers: {
          "x-rapidapi-host": process.env.RAPIDAPI_HOST,
          "x-rapidapi-key": process.env.RAPIDAPI_KEY,
        },
        params: { pid: "1552735248026411010", count: 40 },
      });
      await cacheData("social_twitter_likes", response.data);
      console.log("✅ Social intelligence refreshed");
    } catch (err) {
      console.error("❌ Scheduler twitter update failed:", err.message);
    }
  });
}

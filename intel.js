import express from "express";
import { getCachedData } from "../utils/cache.js";
const router = express.Router();

router.get("/summary", async (_, res) => {
  const [crypto, twitter] = await Promise.all([
    getCachedData("jupiter_intel"),
    getCachedData("social_twitter_likes"),
  ]);

  res.json({
    status: "ok",
    updated: new Date(),
    crypto,
    social: twitter,
  });
});

export default router;

import express from "express";
import axios from "axios";
const router = express.Router();

router.get("/solana", async (_, res) => {
  try {
    const { data } = await axios.get(`${process.env.COINGECKO_BASE_URL}/coins/markets`, {
      params: { vs_currency: "usd", category: "solana-ecosystem" },
    });
    res.json(data.slice(0, 10));
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;

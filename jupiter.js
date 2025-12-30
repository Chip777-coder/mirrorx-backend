import express from "express";
import axios from "axios";

const router = express.Router();
const baseUrl = process.env.JUPITER_API_URL;
const headers = process.env.JUPITER_API_KEY
  ? { "x-api-key": process.env.JUPITER_API_KEY }
  : {};

router.get("/price", async (req, res) => {
  try {
    const { ids } = req.query;
    const { data } = await axios.get(`${baseUrl}/v4/price?ids=${ids || "SOL,USDC,USDT"}`);
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;

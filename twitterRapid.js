import express from "express";
import axios from "axios";
const router = express.Router();

router.get("/likes", async (req, res) => {
  try {
    const { pid, count } = req.query;
    const response = await axios.get(`https://${process.env.RAPIDAPI_HOST}/likes`, {
      headers: {
        "x-rapidapi-host": process.env.RAPIDAPI_HOST,
        "x-rapidapi-key": process.env.RAPIDAPI_KEY,
      },
      params: { pid, count },
    });
    res.json(response.data);
  } catch (error) {
    console.error("❌ Twitter RapidAPI error:", error.message);
    res.status(500).json({ error: "Failed to fetch Twitter likes" });
  }
});

export default router;

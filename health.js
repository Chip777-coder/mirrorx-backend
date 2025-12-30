import express from "express";
const router = express.Router();

router.get("/", (_, res) => {
  res.json({
    status: "ok",
    time: new Date(),
    message: "MirroraX backend operational 🚀"
  });
});

export default router;

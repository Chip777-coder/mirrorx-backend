import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import cryptoRoutes from "./routes/crypto.js";
import jupiterRoutes from "./routes/jupiter.js";
import twitterRapidRoutes from "./routes/twitterRapid.js";
import healthRoutes from "./routes/health.js";
import intelRoutes from "./routes/intel.js";
import { startScheduler } from "./utils/scheduler.js";

dotenv.config();
const app = express();
app.use(cors());
app.use(express.json());

app.use("/crypto", cryptoRoutes);
app.use("/jupiter", jupiterRoutes);
app.use("/twitterRapid", twitterRapidRoutes);
app.use("/health", healthRoutes);
app.use("/intel", intelRoutes);

app.get("/", (req, res) => {
  res.send("🧠 MirroraX Backend — Auto Intelligence Layer Active");
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`);
});

startScheduler();

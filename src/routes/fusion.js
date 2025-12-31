/ routes/fusion.js
import express from "express";
import { getInstitutionalFeed } from "../controllers/fusionController.js";

const router = express.Router();

// this is the route your frontend or GPT will call
router.get("/fusion/market-intel", getInstitutionalFeed);

export default router;

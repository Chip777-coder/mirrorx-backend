import { getCMCListings } from "../services/coinmarketcap.js";
import { getCryptoCompare } from "../services/cryptocompare.js";
import { getDexScreener } from "../services/dexscreener.js";

export async function getInstitutionalFeed(req, res) {
  try {
    const [cmc, cc, dex] = await Promise.all([
      getCMCListings(),
      getCryptoCompare(),
      getDexScreener(),
    ]);

    // Simple normalization example
    const unified = cmc.map((t) => {
      const ccData = cc[t.symbol] || {};
      const dexData = dex.find((d) => d.symbol === t.symbol) || {};

      return {
        symbol: t.symbol,
        name: t.name,
        price: t.quote.USD.price,
        cmcVolume: t.quote.USD.volume_24h,
        ccChange24h: ccData.change24h || 0,
        dexLiquidity: dexData.liquidity?.usd || 0,
        timestamp: new Date().toISOString(),
      };
    });

    res.json({ data: unified, updated: new Date() });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}

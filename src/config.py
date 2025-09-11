    # src/config.py
import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Core
    PORT: int = int(os.getenv("PORT", "10000"))
    FLASK_ENV: str = os.getenv("FLASK_ENV", "production")

    # Database
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # Blockchain / Data APIs
    COINGECKO_API_BASE: str = os.getenv("COINGECKO_API_BASE", "https://api.coingecko.com/api/v3")
    COINMARKETCAP_API_KEY: str = os.getenv("COINMARKETCAP_API_KEY", "")
    DEFILLAMA_API_BASE: str = os.getenv("DEFILLAMA_API_BASE", "https://api.llama.fi")
    DEXSCREENER_API_BASE: str = os.getenv("DEXSCREENER_API_BASE", "https://api.dexscreener.com")
    LUNARCRUSH_API_KEY: str = os.getenv("LUNARCRUSH_API_KEY", "")
    CRYPTOPANIC_API_KEY: str = os.getenv("CRYPTOPANIC_API_KEY", "")
    ALCHEMY_API_KEY: str = os.getenv("ALCHEMY_API_KEY", "")
    MORALIS_API_KEY: str = os.getenv("MORALIS_API_KEY", "")
    SOLSCAN_API_KEY: str = os.getenv("SOLSCAN_API_KEY", "")
    PUSH_API_KEY: str = os.getenv("PUSH_API_KEY", "")
    ANKR_API_KEY: str = os.getenv("ANKR_API_KEY", "")
    SENTIMENT_API_KEY: str = os.getenv("SENTIMENT_API_KEY", "")
    SHYFT_API_KEY: str = os.getenv("SHYFT_API_KEY", "")

    # Optional: QuickNode
    QUICKNODE_HTTP: str = os.getenv("QUICKNODE_HTTP_URL", "")
    QUICKNODE_WSS: str = os.getenv("QUICKNODE_WSS_URL", "")
    USE_ONLY_QUICKNODE: bool = os.getenv("USE_ONLY_QUICKNODE", "0") == "1"

    # RPC Config
    RPC_TIMEOUT_SECS: int = int(os.getenv("RPC_TIMEOUT_SECS", "6"))
    RPC_MAX_WORKERS: int = int(os.getenv("RPC_MAX_WORKERS", "10"))

settings = Settings()

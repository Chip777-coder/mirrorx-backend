# src/config/canonical_tokens.py

# Canonical Solana mints for tokens where symbol collisions/spoofs are common.
# Keep keys uppercase symbols. Values are mint addresses (base token address).
CANONICAL_SOL_MINTS: dict[str, str] = {
    "WEN": "WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk",
    # Add more as you verify them:
    # "BONK": "...",
    # "WIF": "...",
    # "JUP": "...",
}

def canonical_mint_for(symbol: str) -> str | None:
    if not symbol:
        return None
    return CANONICAL_SOL_MINTS.get(symbol.upper())

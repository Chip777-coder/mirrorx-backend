# MirroraX Flask Backend

## 🚀 Overview
A Flask-based backend that powers the MirroraX Intelligence Layer. Combines crypto, social, and external demo APIs for research analysis.

### Key Features
- Crypto (Solana ecosystem) data via CoinGecko & Birdeye
- Jupiter price integration
- Twitter RapidAPI sentiment
- Discord, Telegram, Commerce, Geo, and Weather demo APIs
- Redis caching
- APScheduler background tasks

## ⚙️ Setup
1. Copy `.env.example` to `.env`
2. Create and activate virtual environment:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   python -m src.app
   ```

## 🚀 Deploy on Render
- Environment: Python 3.11+
- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m src.app`
- Port: 10000

## 🌐 Endpoints
| Route | Description |
|--------|-------------|
| `/healthz` | Health check |
| `/crypto/solana` | Solana market data |
| `/jupiter/price` | Jupiter pricing |
| `/twitterRapid/likes` | Twitter RapidAPI likes |
| `/discord/demo` | Discord demo sentiment |
| `/telegram/demo` | Telegram mentions demo |
| `/commerce/demo` | Product demo |
| `/geo/demo` | Geo location demo |
| `/weather/demo` | Open-Meteo weather demo |
| `/intel/full` | Aggregated intelligence snapshot |

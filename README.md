# MirroraX Backend Extended

## 🚀 Overview
This backend provides the MirroraX intelligence layer — combining crypto, social, sentiment, commerce, and geo intelligence data.

### Key Features
- Crypto (Solana ecosystem) data via CoinGecko and Birdeye
- Jupiter price integration
- Twitter RapidAPI sentiment
- Discord, Telegram, Commerce, Geo, and Weather demo APIs
- Redis caching
- Automatic intelligence scheduler

## ⚙️ Setup
1. Copy `.env.example` to `.env`
2. Run `npm install`
3. Start server: `npm start`

## 🌐 Endpoints
| Route | Description |
|-------|--------------|
| `/crypto/solana` | Solana market data |
| `/jupiter/price` | Jupiter pricing |
| `/twitterRapid/likes` | Twitter RapidAPI likes |
| `/discord/demo` | Discord demo sentiment |
| `/telegram/demo` | Telegram mentions demo |
| `/commerce/demo` | Amazon/FlashAPI product demo |
| `/geo/demo` | Geo location demo |
| `/weather/demo` | Open-Meteo weather demo |
| `/intel/full` | Aggregated intelligence snapshot |

## 🚀 Deploy on Render
- Node Version: 18.x
- Build Command: `npm install`
- Start Command: `npm start`

## 🧠 Notes
All demo endpoints can be swapped for real APIs by updating `.env` with production keys.

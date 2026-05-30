# CryptoAI Trader

AI-powered crypto trading agent with mobile app. Supports Spot, Grid, Futures, and Perpetual trading on Binance, OKX, and Hyperliquid.

## Architecture

```
crypto-ai-trader/
├── backend/          # FastAPI + Python AI Agent
│   ├── app/
│   │   ├── agent/   # AI Trading Agent (Claude-powered)
│   │   ├── exchanges/  # Binance, OKX, Hyperliquid clients
│   │   └── api/     # REST + WebSocket endpoints
│   └── Dockerfile
├── mobile/           # React Native App
│   └── src/
│       ├── screens/ # Dashboard, Trading, Portfolio, Wallet, Settings
│       ├── components/
│       └── services/ # API + WebSocket client
└── docker-compose.yml
```

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your API keys

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Or with Docker:
```bash
cp backend/.env.example .env
docker-compose up -d
```

### Mobile App

```bash
cd mobile
npm install
npx react-native run-ios    # iOS
npx react-native run-android  # Android
```

## Configuration

Set these in `backend/.env`:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude AI API key (required) |
| `BINANCE_API_KEY` | Binance API key |
| `BINANCE_SECRET_KEY` | Binance secret |
| `BINANCE_TESTNET` | Use testnet (true/false) |
| `OKX_API_KEY` | OKX API key |
| `OKX_SECRET_KEY` | OKX secret |
| `OKX_PASSPHRASE` | OKX passphrase |
| `HYPERLIQUID_PRIVATE_KEY` | ETH wallet private key |

## Trading Strategies

### Spot Trading
Buy/sell assets directly. AI analyzes RSI, MACD, EMA crossovers across 1H and 4H timeframes.

### Grid Trading
Automatically places buy/sell orders at fixed price intervals. Profits from price oscillation.
- AI calculates optimal upper/lower bounds based on ATR volatility
- Rebalances automatically when orders fill

### Futures / Perpetual
Leveraged positions with configurable leverage (default 3x, max 10x).
- Full long/short capability
- Automatic TP/SL placement
- Risk-managed position sizing

## Risk Management

- Maximum position size: 5% of portfolio per trade
- Maximum drawdown: 15% triggers agent pause
- Stop-loss required on every trade
- Paper trading mode for testing (default: ON)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/health` | Health check |
| `GET /api/v1/prices` | Live prices |
| `GET /api/v1/market/{exchange}/{symbol}` | Full market analysis |
| `POST /api/v1/agent/analyze` | AI analysis + decision |
| `POST /api/v1/agent/start` | Start auto-trading |
| `POST /api/v1/agent/stop` | Stop agent |
| `GET /api/v1/portfolio/{exchange}` | Portfolio balances |
| `POST /api/v1/grid/setup` | Calculate grid parameters |
| `WS /ws` | Real-time prices + agent status |

## Security

- API keys stored encrypted on device
- WalletConnect for on-chain signing (no private key exposure)
- Testnet mode enabled by default
- Read-only portfolio viewing supported (no trade keys required)

## Disclaimer

This software is for educational purposes. Crypto trading involves significant risk of loss. Always test with paper trading before using real funds. Past AI performance does not guarantee future results.

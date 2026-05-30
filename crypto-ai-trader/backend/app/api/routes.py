import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from app.agent.trading_agent import TradingAgent
from app.agent.market_analyzer import compute_indicators, calculate_grid_params

router = APIRouter()
agent = TradingAgent()
agent_task: Optional[asyncio.Task] = None


class AgentConfig(BaseModel):
    watchlist: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    exchanges: List[str] = ["binance"]
    risk_level: str = "medium"
    portfolio_value: float = 10000.0
    use_paper: bool = True
    interval_minutes: int = 60


class GridSetupRequest(BaseModel):
    exchange: str
    symbol: str
    investment: float
    grid_count: int = 10
    upper_price: Optional[float] = None
    lower_price: Optional[float] = None


class OrderRequest(BaseModel):
    exchange: str
    symbol: str
    side: str
    amount: float
    price: Optional[float] = None
    leverage: int = 1
    strategy: str = "spot"


_agent_config = AgentConfig()
_is_running = False


async def run_agent_loop(config: AgentConfig):
    global _is_running
    _is_running = True
    while _is_running:
        try:
            results = await agent.run_cycle(
                config.watchlist,
                config.exchanges,
                config.portfolio_value,
                config.risk_level,
                config.use_paper,
            )
            print(f"[Agent] Cycle complete: {len(results)} analyses")
        except Exception as e:
            print(f"[Agent] Error: {e}")
        await asyncio.sleep(config.interval_minutes * 60)


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.post("/agent/start")
async def start_agent(config: AgentConfig, background_tasks: BackgroundTasks):
    global agent_task, _agent_config, _is_running
    if _is_running:
        return {"status": "already_running"}
    _agent_config = config
    background_tasks.add_task(run_agent_loop, config)
    return {"status": "started", "config": config.dict()}


@router.post("/agent/stop")
async def stop_agent():
    global _is_running
    _is_running = False
    return {"status": "stopped"}


@router.get("/agent/status")
async def agent_status():
    return {
        "is_running": _is_running,
        "paper_balance": agent.paper_balance,
        "paper_positions": agent.paper_positions,
        "config": _agent_config.dict(),
    }


@router.get("/market/{exchange}/{symbol}")
async def get_market_data(exchange: str, symbol: str):
    try:
        symbol = symbol.replace("-", "/").upper()
        data = await agent.analyze_market(symbol, exchange)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/agent/analyze")
async def analyze_and_decide(exchange: str, symbol: str, portfolio_value: float = 10000, risk_level: str = "medium"):
    try:
        symbol = symbol.upper()
        market_data = await agent.analyze_market(symbol, exchange)
        decision = await agent.get_ai_decision(market_data, portfolio_value, risk_level)
        return {
            "market_data": market_data,
            "decision": decision,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/portfolio/{exchange}")
async def get_portfolio(exchange: str):
    try:
        if exchange == "binance":
            balance = await agent.binance.get_balance()
            positions = await agent.binance.get_positions()
        elif exchange == "okx":
            balance = await agent.okx.get_balance()
            positions = await agent.okx.get_positions()
        elif exchange == "hyperliquid":
            state = await agent.hyperliquid.get_user_state()
            balance = state
            positions = []
        elif exchange == "paper":
            balance = agent.paper_balance
            positions = agent.paper_positions
        else:
            raise HTTPException(status_code=400, detail="Unknown exchange")
        return {"exchange": exchange, "balance": balance, "positions": positions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/grid/setup")
async def setup_grid(req: GridSetupRequest):
    try:
        if req.exchange == "binance":
            ticker = await agent.binance.get_ticker(req.symbol)
        elif req.exchange == "okx":
            ticker = await agent.okx.get_ticker(req.symbol)
        else:
            raise HTTPException(status_code=400, detail="Grid not supported for this exchange")

        current_price = ticker["price"]
        ohlcv = await agent.binance.get_ohlcv(req.symbol, "1d", 30)
        indicators = compute_indicators(ohlcv)
        volatility = indicators.get("atr_pct", 3)

        grid_params = calculate_grid_params(
            req.upper_price or current_price,
            volatility,
            req.investment,
            req.grid_count,
        )
        if req.upper_price:
            grid_params["upper_price"] = req.upper_price
        if req.lower_price:
            grid_params["lower_price"] = req.lower_price

        return {
            "symbol": req.symbol,
            "exchange": req.exchange,
            "current_price": current_price,
            "grid_params": grid_params,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trade/manual")
async def manual_trade(req: OrderRequest):
    try:
        symbol = req.symbol.upper()
        if req.exchange == "binance":
            if req.strategy == "spot":
                result = await agent.binance.place_spot_order(symbol, req.side, req.amount, req.price)
            else:
                result = await agent.binance.place_futures_order(symbol, req.side, req.amount, req.leverage, req.price)
        elif req.exchange == "okx":
            if req.strategy == "spot":
                result = await agent.okx.place_spot_order(symbol, req.side, req.amount, req.price)
            else:
                result = await agent.okx.place_perpetual_order(symbol, req.side, req.amount, req.leverage, req.price)
        elif exchange == "paper":
            result = {"status": "paper", "message": "Use agent analyze endpoint"}
        else:
            raise HTTPException(status_code=400, detail="Unknown exchange")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/prices")
async def get_prices(symbols: str = "BTC/USDT,ETH/USDT,SOL/USDT"):
    symbol_list = [s.strip() for s in symbols.split(",")]
    prices = {}
    for symbol in symbol_list:
        try:
            ticker = await agent.binance.get_ticker(symbol)
            prices[symbol] = ticker
        except Exception as e:
            prices[symbol] = {"error": str(e)}
    return prices

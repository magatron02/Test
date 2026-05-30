from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router, agent
from app.api.websocket import websocket_endpoint
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    yield
    await agent.close()
    print("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket, agent)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "ws": "/ws",
    }

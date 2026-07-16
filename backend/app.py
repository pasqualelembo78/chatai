"""ChatAI FastAPI application — slim entry point."""

import os
import sys
import logging
import threading
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio as socketio_lib

from storage import init_db, init_group_chat_tables
from ai_engine import init_provider, rebuild_free_model_chain
from auth_fastapi import init_auth_db, _cleanup_expired_tokens

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Rate limiter ────────────────────────────────────────────────
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

# ─── Socket.IO ───────────────────────────────────────────────────
sio = socketio_lib.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=30,
    ping_timeout=120,
    logger=False,
    engineio_logger=False,
)

# ─── Background helpers ──────────────────────────────────────────
def _cleanup_loop():
    import audio_utils, security_utils
    while True:
        time.sleep(300)
        try:
            audio_utils.cleanup_old_files()
        except Exception:
            pass
        try:
            security_utils.cleanup_old_files()
        except Exception:
            pass

def _free_port_background(port):
    import subprocess, signal
    try:
        own_pid = os.getpid()
        time.sleep(1)
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split() if int(p) != own_pid]
            if pids:
                logger.warning(f"Port {port} in use by PIDs: {pids}. Killing...")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                time.sleep(1)
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
    except Exception:
        pass

def _free_port(port):
    import subprocess, signal
    try:
        own_pid = os.getpid()
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split() if int(p) != own_pid]
            if pids:
                logger.warning(f"Port {port} in use by PIDs: {pids}. Killing...")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                time.sleep(1)
    except Exception:
        pass

# ─── Lifespan ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application):
    logger.info("Initializing database...")
    init_db()
    init_auth_db()
    init_group_chat_tables()
    init_provider()
    rebuild_free_model_chain()
    threading.Thread(target=_cleanup_loop, daemon=True).start()
    threading.Thread(target=_cleanup_expired_tokens, daemon=True).start()
    threading.Thread(target=_free_port_background, args=(int(os.environ.get("PORT", 5000)),), daemon=True).start()
    logger.info("ChatAI FastAPI started")
    yield
    logger.info("ChatAI FastAPI shutting down")

# ─── FastAPI app ─────────────────────────────────────────────────
app = FastAPI(title="ChatAI", docs_url="/docs", redoc_url=None, lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ─── Include routers ─────────────────────────────────────────────
from app_routes.public import router as public_router
from app_routes.auth import router as auth_router
from app_routes.characters import router as characters_router
from app_routes.memory import router as memory_router
from app_routes.conversations import router as conversations_router
from app_routes.premium import router as premium_router
from app_routes.admin import router as admin_router
from app_routes.group_chat import router as group_chat_router
from app_routes.chat import router as chat_router

app.include_router(public_router)
app.include_router(auth_router)
app.include_router(characters_router)
app.include_router(memory_router)
app.include_router(conversations_router)
app.include_router(premium_router)
app.include_router(admin_router)
app.include_router(group_chat_router)
app.include_router(chat_router)

# ─── Socket.IO ───────────────────────────────────────────────────
from app_socket import register_socket_handlers
register_socket_handlers(sio)

socket_app = socketio_lib.ASGIApp(sio, other_asgi_app=app)

# ─── Entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    _free_port(port)
    logger.info(f"Starting on port {port}...")
    uvicorn.run("app:socket_app", host="0.0.0.0", port=port, reload=False, log_level="info")

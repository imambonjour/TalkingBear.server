from fastapi import WebSocket
from config import DEVICE_SECRET_KEY
import logging

logger = logging.getLogger(__name__)


async def validate_device_key(websocket: WebSocket) -> bool:
    """
    Validasi device key dari header WebSocket.
    Jika DEVICE_SECRET_KEY tidak di-set di .env, skip validasi (untuk testing).
    """
    if not DEVICE_SECRET_KEY:
        logger.warning("DEVICE_SECRET_KEY not set, skipping auth (dev mode)")
        return True

    device_key = websocket.headers.get("X-Device-Key")
    if device_key != DEVICE_SECRET_KEY:
        logger.warning(f"Unauthorized device key: {device_key}")
        await websocket.close(code=4001, reason="Unauthorized")
        return False

    return True

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
log_dir = os.getenv("LOG_DIR", "/var/www/gitboss-ai/agent-dev/logs")
log_level = os.getenv("LOG_LEVEL", "INFO")

os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s %(levelname)s:%(message)s",
    level=getattr(logging, log_level),
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "websocket.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "8003"))

# Import WebSocket handler
from websocket_handler import WebSocketHandler

# Create WebSocket handler instance
ws_handler = WebSocketHandler()

# ASGI application
async def application(scope, receive, send):
    """
    ASGI application entry point for Gunicorn
    Only handles WebSocket connections, returns 404 for everything else
    """
    logger.info(f"Received {scope['type']} request to {scope.get('path', 'unknown path')}")
    
    if scope["type"] == "websocket":
        # Handle WebSocket connections
        await ws_handler.handle_websocket(scope, receive, send)
    elif scope["type"] == "http":
        # Return 404 for HTTP requests
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain")]
        })
        await send({
            "type": "http.response.body",
            "body": b"Not Found - WebSocket endpoint only"
        })
    elif scope["type"] == "lifespan":
        # Handle lifespan events
        message = await receive()
        if message["type"] == "lifespan.startup":
            logger.info("Lifespan startup event")
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            logger.info("Lifespan shutdown event")
            await send({"type": "lifespan.shutdown.complete"})

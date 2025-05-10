import json
import logging
import asyncio
from typing import Dict
import websockets
from websockets.exceptions import ConnectionClosed

# Import custom modules
from ai_agent import AIAgent
from jwt_validator import JWTValidator

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """
    Handler for WebSocket connections using ASGI interface
    """

    def __init__(self):
        self.active_connections: Dict[str, object] = {}
        self.ai_agent = AIAgent()
        self.jwt_validator = JWTValidator()
        logger.info("WebSocket handler initialized")

    async def handle_websocket(self, scope, receive, send):
        """
        Handle WebSocket connection using ASGI interface
        """
        user_id = None
        
        try:
            # Accept the WebSocket connection
            await send({"type": "websocket.accept"})
            logger.info("WebSocket connection accepted")
            
            # Extract token from query string
            query_string = scope.get("query_string", b"").decode("utf-8")
            path = scope.get("path", "")
            logger.info(f"Path: {path}, Query string: {query_string}")
            
            params = {}
            if query_string:
                try:
                    params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
                except Exception as e:
                    logger.error(f"Error parsing query string: {e}")
            
            token = params.get('token', '')
            
            if not token:
                logger.warning("No token provided")
                await send({"type": "websocket.send", "text": json.dumps({"error": "Authentication required"})})
                await send({"type": "websocket.close", "code": 1008, "reason": "Authentication required"})
                return
                
            # Validate the token
            logger.info(f"Validating token (length: {len(token)})")
            payload = self.jwt_validator.validate_token(token)
            if not payload:
                logger.warning("Invalid or expired token")
                await send({"type": "websocket.send", "text": json.dumps({"error": "Invalid or expired token"})})
                await send({"type": "websocket.close", "code": 1008, "reason": "Authentication failed"})
                return
                
            # Extract user ID from payload
            user_id = str(payload.get("sub", ""))
            username = payload.get("username", "Unknown")
            
            if not user_id:
                logger.warning("Token missing user ID")
                await send({"type": "websocket.send", "text": json.dumps({"error": "Invalid token format"})})
                await send({"type": "websocket.close", "code": 1008, "reason": "Authentication failed"})
                return
                
            logger.info(f"Authenticated connection for user {username} (ID: {user_id})")
            
            # Store connection info in memory
            self.active_connections[user_id] = (send, receive)
            
            # Send confirmation
            await send({
                "type": "websocket.send", 
                "text": json.dumps({
                    "type": "connection_successful",
                    "user_id": user_id,
                    "username": username
                })
            })
            
            # Process messages
            while True:
                message = await receive()
                
                if message["type"] == "websocket.disconnect":
                    logger.info(f"Connection closed for user {username} (ID: {user_id})")
                    break
                    
                if message["type"] == "websocket.receive":
                    # Get message content
                    message_text = message.get("text", "")
                    if not message_text and "bytes" in message:
                        message_text = message["bytes"].decode("utf-8")
                    
                    logger.info(f"Received message from {username} (ID: {user_id}): {message_text}")
                    
                    # Echo back for now - we'll add AI processing later
                    response = json.dumps({
                        "type": "response",
                        "content": "Hi from Gitboss AI"
                    })
                    
                    # Send response back to client
                    await send({"type": "websocket.send", "text": response})
                
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}", exc_info=True)
        finally:
            # Clean up connection from memory
            if user_id and user_id in self.active_connections:
                del self.active_connections[user_id]
                logger.info(f"Removed connection for user {user_id}")

    async def broadcast_message(self, message: str):
        """
        Broadcast a message to all connected clients
        """
        if not self.active_connections:
            return
        
        for user_id, (send, _) in self.active_connections.items():
            try:
                await send({"type": "websocket.send", "text": message})
            except Exception as e:
                logger.error(f"Error sending to {user_id}: {e}")

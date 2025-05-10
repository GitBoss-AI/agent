import json
import logging

# Set up logger
logger = logging.getLogger(__name__)

class AIAgent:
    """
    Simple AI Agent that just echoes back messages
    """
    
    def __init__(self):
        logger.info("Echo AI Agent initialized")
    
    async def process_message(self, message: str, client_id: str) -> str:
        """
        Simply echo the message back to the client
        """
        logger.info(f"Echoing message from client {client_id}")
        
        try:
            # Try to parse as JSON
            data = json.loads(message)
            content = data.get("content", message)
            
            # Create a response JSON
            response = {
                "type": "response",
                "content": f"Echo: {content}",
                "clientId": client_id
            }
            
            return json.dumps(response)
            
        except json.JSONDecodeError:
            # If not JSON, just echo as plain text
            return json.dumps({
                "type": "response",
                "content": f"Echo: {message}",
                "clientId": client_id
            })

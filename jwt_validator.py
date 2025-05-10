import json
import logging
import base64
import hmac
import hashlib
import os
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class JWTValidator:
    """
    Class for validating JWT tokens issued by the PHP backend
    """
    
    def __init__(self, secret=None):
        """
        Initialize the JWT validator
        
        Args:
            secret: The secret key to use for validation. If not provided, uses JWT_SECRET from env
        """
        self.secret = secret or os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
        logger.info("JWT Validator initialized")
    
    def validate_token(self, token: str) -> Optional[dict]:
        """
        Validate a JWT token and return the payload if valid
        
        Args:
            token: The JWT token to validate
            
        Returns:
            dict: The token payload if valid, None if invalid
        """
        try:
            # Split the token into header, payload, and signature
            header_b64, payload_b64, signature_b64 = token.split('.')
            
            # Verify signature
            message = f"{header_b64}.{payload_b64}"
            signature = self._base64_url_decode(signature_b64)
            
            expected_signature = hmac.new(
                self.secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Invalid JWT signature")
                return None
            
            # Decode payload
            payload_json = self._base64_url_decode(payload_b64).decode('utf-8')
            payload = json.loads(payload_json)
            
            logger.info(f"Decoded payload: {payload}")
            
            # Map non-standard claims to standard ones
            standardized_payload = {
                # Use standard claims if present, otherwise use non-standard ones
                "sub": payload.get("sub") or payload.get("subject"),
                "exp": payload.get("exp") or payload.get("expiration"),
                "iat": payload.get("iat") or payload.get("issuedAt"),
                # Keep the username field
                "username": payload.get("username", "Unknown")
            }
            
            # Check expiration
            exp_time = standardized_payload["exp"]
            if exp_time and float(exp_time) < datetime.now().timestamp():
                logger.warning(f"JWT token has expired at {exp_time}")
                return None
            
            return standardized_payload
        except Exception as e:
            logger.error(f"JWT validation error: {e}", exc_info=True)
            return None
    
    def _base64_url_decode(self, input: str) -> bytes:
        """
        Decode base64url-encoded string (compatible with PHP implementation)
        
        Args:
            input: The base64url encoded string
            
        Returns:
            bytes: The decoded data
        """
        # Replace URL-safe characters
        input = input.replace('-', '+').replace('_', '/')
        
        # Add padding if needed
        pad = len(input) % 4
        if pad:
            input += '=' * (4 - pad)
            
        return base64.b64decode(input)

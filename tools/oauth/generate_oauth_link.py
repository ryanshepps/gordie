"""Tool to generate Yahoo OAuth link for user authentication."""

import os
import secrets
from urllib.parse import urlencode
from langchain.tools import tool
from pydantic import BaseModel, Field
from client.DuckDbClient import get_platform_db_connection
from module.logger import get_logger


logger = get_logger(__name__)


class GenerateOAuthLinkInput(BaseModel):
    user_email: str = Field(description="User's email address to associate with the OAuth flow")


@tool(args_schema=GenerateOAuthLinkInput)
def generate_oauth_link(user_email: str) -> str:
    """
    Generate a Yahoo OAuth authorization link for the user to authenticate.
    
    This tool creates a unique OAuth URL that the user should click to authorize
    the application to access their Yahoo Fantasy account.
    
    Args:
        user_email: User's email address to track the OAuth flow
    
    Returns:
        The OAuth authorization URL as a string, or an error message if configuration is missing.
    """
    client_id = os.getenv("YAHOO_CLIENT_ID")
    oauth_base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:8000")
    
    if not client_id:
        error_msg = "OAuth configuration error: YAHOO_CLIENT_ID not found. Please contact support."
        logger.error(error_msg)
        return error_msg
    
    # Generate a unique nonce for security
    nonce = secrets.token_urlsafe(32)
    
    # Store nonce in database for later retrieval during callback
    _store_oauth_nonce(user_email, nonce)
    
    # Build callback URL
    callback_url = f"{oauth_base_url.rstrip('/')}/callback"
    
    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email fspt-r",  # openid, email, and fantasy sports read
        "nonce": nonce,
        "state": user_email,  # Pass user_email via state parameter
        "language": "en-us"
    }
    
    auth_url = f"https://api.login.yahoo.com/oauth2/request_auth?{urlencode(params)}"
    
    logger.info(f"Generated OAuth link for user {user_email} with callback: {callback_url}")
    
    return auth_url


def _store_oauth_nonce(user_email: str, nonce: str) -> None:
    """Store OAuth nonce in database for later retrieval."""
    conn = get_platform_db_connection()
    try:
        # Create table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_nonces (
                user_email TEXT PRIMARY KEY,
                nonce TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Store or update nonce
        conn.execute("""
            INSERT OR REPLACE INTO oauth_nonces (user_email, nonce, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_email, nonce))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to store OAuth nonce: {e}")
        raise
    finally:
        conn.close()

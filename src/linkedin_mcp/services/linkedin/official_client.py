"""
LinkedIn Official API Client using OAuth 2.0.

This client uses LinkedIn's official API with proper OAuth authentication,
providing reliable access to user profile data without the challenges
of the unofficial Voyager API.
"""
import json
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse
import threading

import requests
import structlog

logger = structlog.get_logger()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from LinkedIn."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_GET(self):
        """Handle the OAuth callback GET request."""
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        if 'code' in query_params:
            self.server.auth_code = query_params['code'][0]
            self.server.auth_state = query_params.get('state', [None])[0]

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>LinkedIn Authorization</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                        text-align: center;
                        padding: 60px 20px;
                        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
                        min-height: 100vh;
                        margin: 0;
                        box-sizing: border-box;
                    }
                    .container {
                        background: white;
                        border-radius: 12px;
                        padding: 40px;
                        max-width: 480px;
                        margin: 0 auto;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    }
                    .checkmark {
                        width: 64px;
                        height: 64px;
                        background: #0a66c2;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 24px;
                    }
                    .checkmark svg {
                        width: 32px;
                        height: 32px;
                        fill: white;
                    }
                    h1 {
                        color: #0a66c2;
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0 0 12px;
                    }
                    p {
                        color: #666;
                        font-size: 16px;
                        margin: 0;
                    }
                    .scopes {
                        margin-top: 24px;
                        padding-top: 24px;
                        border-top: 1px solid #e0e0e0;
                        text-align: left;
                    }
                    .scopes h3 {
                        font-size: 14px;
                        color: #333;
                        margin: 0 0 12px;
                        font-weight: 600;
                    }
                    .scope-item {
                        display: flex;
                        align-items: center;
                        padding: 8px 0;
                        font-size: 13px;
                        color: #555;
                    }
                    .scope-item svg {
                        width: 16px;
                        height: 16px;
                        fill: #0a66c2;
                        margin-right: 10px;
                        flex-shrink: 0;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="checkmark">
                        <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                    </div>
                    <h1>Authorization Successful</h1>
                    <p>You can close this window and return to Claude.</p>
                    <div class="scopes">
                        <h3>Permissions Granted:</h3>
                        <div class="scope-item">
                            <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                            <span><strong>openid</strong> — OpenID Connect authentication</span>
                        </div>
                        <div class="scope-item">
                            <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                            <span><strong>profile</strong> — Basic profile information</span>
                        </div>
                        <div class="scope-item">
                            <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                            <span><strong>email</strong> — Email address</span>
                        </div>
                        <div class="scope-item">
                            <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                            <span><strong>w_member_social</strong> — Create and manage posts</span>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
        elif 'error' in query_params:
            self.server.auth_error = query_params.get('error_description', query_params['error'])[0]

            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>LinkedIn Authorization Failed</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                        text-align: center;
                        padding: 60px 20px;
                        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
                        min-height: 100vh;
                        margin: 0;
                        box-sizing: border-box;
                    }}
                    .container {{
                        background: white;
                        border-radius: 12px;
                        padding: 40px;
                        max-width: 480px;
                        margin: 0 auto;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    }}
                    .error-icon {{
                        width: 64px;
                        height: 64px;
                        background: #dc3545;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 24px;
                    }}
                    .error-icon svg {{
                        width: 32px;
                        height: 32px;
                        fill: white;
                    }}
                    h1 {{
                        color: #dc3545;
                        font-size: 24px;
                        font-weight: 600;
                        margin: 0 0 12px;
                    }}
                    p {{
                        color: #666;
                        font-size: 16px;
                        margin: 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">
                        <svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                    </div>
                    <h1>Authorization Failed</h1>
                    <p>{self.server.auth_error}</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())


class LinkedInOfficialClient:
    """
    LinkedIn Official API Client using OAuth 2.0.

    This client provides reliable access to LinkedIn's official API endpoints
    using proper OAuth 2.0 authentication flow.

    Available endpoints with current scopes (openid, profile, email):
    - /v2/userinfo: Get authenticated user's profile (name, email, picture)

    To enable more features, request additional products in the LinkedIn Developer Portal:
    - "Share on LinkedIn": Enables posting content (w_member_social scope)
    - "Advertising API": Marketing and analytics
    """

    # OAuth endpoints
    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    API_BASE = "https://api.linkedin.com/v2"

    # Default scopes for Sign In with LinkedIn using OpenID Connect
    DEFAULT_SCOPES = ["openid", "profile", "email"]

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8765/callback",
        token_path: Optional[Path] = None,
        scopes: Optional[list[str]] = None,
    ):
        """
        Initialize the LinkedIn Official API client.

        Args:
            client_id: LinkedIn app client ID
            client_secret: LinkedIn app client secret
            redirect_uri: OAuth callback URL (must be registered in LinkedIn Developer Portal)
            token_path: Path to store OAuth tokens
            scopes: OAuth scopes to request (defaults to openid, profile, email)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_path = token_path or Path("data/oauth_token.json")
        self.scopes = scopes or self.DEFAULT_SCOPES

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[int] = None
        self._session = requests.Session()

        # Load existing token if available
        self._load_token()

    def _load_token(self) -> bool:
        """Load token from file if it exists and is valid."""
        if not self.token_path.exists():
            return False

        try:
            with open(self.token_path) as f:
                data = json.load(f)

            expires_at = data.get("expires_at", 0)
            if expires_at > time.time() + 300:  # 5 minute buffer
                self._access_token = data["access_token"]
                self._token_expires_at = expires_at
                logger.info("Loaded existing OAuth token", expires_in=int(expires_at - time.time()))
                return True
            else:
                logger.info("OAuth token expired or expiring soon")
                return False
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning("Failed to load OAuth token", error=str(e))
            return False

    def _save_token(self, token_data: dict) -> None:
        """Save token to file."""
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info("Saved OAuth token", path=str(self.token_path))

    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid access token."""
        if not self._access_token:
            return False
        if self._token_expires_at and self._token_expires_at <= time.time():
            return False
        return True

    def get_authorization_url(
        self, state: Optional[str] = None, force_consent: bool = False
    ) -> str:
        """
        Generate the OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection
            force_consent: If True, adds prompt=consent to force the consent screen
                          to appear even if user has already authorized the app

        Returns:
            Authorization URL to redirect the user to
        """
        import secrets
        state = state or secrets.token_urlsafe(16)

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }

        # Add prompt=consent to force the consent screen (OIDC standard parameter)
        # This ensures the user sees the permissions being requested
        if force_consent:
            params["prompt"] = "consent"

        return f"{self.AUTH_URL}?{urlencode(params)}"

    def authenticate_interactive(
        self, timeout: int = 120, force_consent: bool = False
    ) -> bool:
        """
        Start interactive OAuth flow with local callback server.

        This opens the browser for the user to authenticate and handles
        the callback automatically.

        Args:
            timeout: Maximum seconds to wait for authentication
            force_consent: If True, forces LinkedIn to show the consent screen
                          even if user has already authorized the app

        Returns:
            True if authentication was successful
        """
        import secrets
        state = secrets.token_urlsafe(16)

        # Parse the redirect URI to get host and port
        parsed = urlparse(self.redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8765

        # Create callback server
        server = HTTPServer((host, port), OAuthCallbackHandler)
        server.auth_code = None
        server.auth_state = None
        server.auth_error = None
        server.timeout = timeout

        # Generate auth URL and open browser
        auth_url = self.get_authorization_url(state, force_consent=force_consent)
        logger.info("Opening browser for LinkedIn authentication...")
        webbrowser.open(auth_url)

        # Wait for callback
        logger.info(f"Waiting for OAuth callback on {self.redirect_uri}...")

        def handle_timeout():
            time.sleep(timeout)
            server.shutdown()

        timeout_thread = threading.Thread(target=handle_timeout, daemon=True)
        timeout_thread.start()

        try:
            while server.auth_code is None and server.auth_error is None:
                server.handle_request()
        except Exception as e:
            logger.error("OAuth callback error", error=str(e))
            return False
        finally:
            server.server_close()

        if server.auth_error:
            logger.error("OAuth authentication failed", error=server.auth_error)
            return False

        if server.auth_code:
            # Verify state
            if server.auth_state != state:
                logger.error("OAuth state mismatch - possible CSRF attack")
                return False

            # Exchange code for token
            return self.exchange_code(server.auth_code)

        logger.error("OAuth authentication timed out")
        return False

    def exchange_code(self, code: str) -> bool:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            True if token exchange was successful
        """
        try:
            response = self._session.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if not response.ok:
                logger.error("Token exchange failed", status=response.status_code, body=response.text)
                return False

            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 5184000)  # Default 60 days
            self._token_expires_at = int(time.time() + expires_in)

            # Save token
            token_data = {
                "access_token": self._access_token,
                "token_type": data.get("token_type", "Bearer"),
                "expires_at": self._token_expires_at,
                "scopes": self.scopes,
                "created_at": int(time.time()),
            }
            self._save_token(token_data)

            logger.info("OAuth authentication successful", expires_in=expires_in)
            return True

        except Exception as e:
            logger.error("Token exchange error", error=str(e))
            return False

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "X-RestLi-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def _api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Make an API request to LinkedIn.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data

        Returns:
            Response JSON data or None on error
        """
        if not self.is_authenticated:
            logger.error("Not authenticated - call authenticate_interactive() first")
            return None

        url = f"{self.API_BASE}/{endpoint.lstrip('/')}"

        try:
            response = self._session.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                params=params,
                json=data,
            )

            if response.ok:
                return response.json() if response.text else {}
            else:
                logger.error(
                    "API request failed",
                    endpoint=endpoint,
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except Exception as e:
            logger.error("API request error", endpoint=endpoint, error=str(e))
            return None

    # ==================== API Methods ====================

    def get_user_info(self) -> Optional[dict[str, Any]]:
        """
        Get the authenticated user's profile information.

        This uses the OpenID Connect userinfo endpoint which provides:
        - sub: User's LinkedIn ID
        - name: Full name
        - given_name: First name
        - family_name: Last name
        - picture: Profile picture URL
        - email: Email address (if email scope is granted)
        - email_verified: Whether email is verified

        Returns:
            User info dict or None on error
        """
        if not self.is_authenticated:
            return None

        try:
            response = self._session.get(
                f"{self.API_BASE}/userinfo",
                headers=self._get_headers(),
            )

            if response.ok:
                return response.json()
            else:
                logger.error("Failed to get user info", status=response.status_code)
                return None
        except Exception as e:
            logger.error("Error getting user info", error=str(e))
            return None

    def get_my_profile(self) -> Optional[dict[str, Any]]:
        """
        Get the authenticated user's profile in a format compatible with the MCP tools.

        Returns a normalized profile dict with these fields:
        - id: LinkedIn member ID
        - first_name: First name
        - last_name: Last name
        - name: Full name
        - email: Email address
        - picture_url: Profile picture URL
        - headline: Job title/headline (if available)

        Returns:
            Profile dict or None on error
        """
        user_info = self.get_user_info()
        if not user_info:
            return None

        return {
            "id": user_info.get("sub"),
            "first_name": user_info.get("given_name"),
            "last_name": user_info.get("family_name"),
            "name": user_info.get("name"),
            "email": user_info.get("email"),
            "email_verified": user_info.get("email_verified"),
            "picture_url": user_info.get("picture"),
            "headline": None,  # Not available with OpenID Connect
            "source": "official_api",
        }

    def debug_context(self) -> dict[str, Any]:
        """
        Get debug information about the client state.

        Returns:
            Dict with client status information
        """
        return {
            "client_type": "official",
            "authenticated": self.is_authenticated,
            "token_expires_at": self._token_expires_at,
            "token_valid_for": int(self._token_expires_at - time.time()) if self._token_expires_at else 0,
            "scopes": self.scopes,
            "api_base": self.API_BASE,
            "available_features": [
                "get_user_info",
                "get_my_profile",
            ],
            "unavailable_features": [
                "get_feed (requires Share on LinkedIn product)",
                "search_people (not available in official API)",
                "get_connections (requires additional permissions)",
                "send_message (requires additional permissions)",
                "create_post (requires Share on LinkedIn product)",
            ],
        }

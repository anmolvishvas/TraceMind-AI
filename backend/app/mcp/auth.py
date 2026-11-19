"""Authentication and authorization controls for the TraceMind Model Context Protocol (MCP) server."""

from __future__ import annotations

import logging
import secrets

from app.core.config import get_settings

logger = logging.getLogger("tracemind.mcp.auth")


class MCPAuthError(Exception):
    """Raised when an MCP client fails authentication or lacks required tool permissions."""


class MCPAuthenticator:
    """
    Validates MCP tool invocation credentials and enforces read-only access boundaries.
    """

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.expected_key = api_key or settings.MCP_API_KEY

    def verify_token(self, token: str | None) -> bool:
        """
        Validate authentication token against configured secret key in constant time.
        Allows unauthenticated access only if explicitly in local development/test mode.
        """
        if not token:
            settings = get_settings()
            if settings.ENVIRONMENT in ("development", "test"):
                return True
            return False

        return secrets.compare_digest(token, self.expected_key)

    def authorize_read_access(self, token: str | None) -> None:
        """
        Enforce that callers possess valid read-only authorization.
        """
        if not self.verify_token(token):
            raise MCPAuthError(
                "Unauthorized: Invalid or missing TraceMind MCP authentication token."
            )

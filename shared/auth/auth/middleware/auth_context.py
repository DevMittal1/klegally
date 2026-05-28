import contextvars
from typing import Optional, Dict, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from auth.jwt.verification import verify_access_token

# Context variable to hold user auth payload
_auth_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "auth_context", default=None
)


def get_auth_context() -> Optional[Dict[str, Any]]:
    """Get the current authenticated user context payload."""
    return _auth_context.get()


def set_auth_context(payload: Optional[Dict[str, Any]]) -> contextvars.Token:
    """Set the current authenticated user context payload."""
    return _auth_context.set(payload)


class AuthContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts the Bearer token from the Authorization header,
    verifies it, and stores the payload in a context variable.
    """
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        authorization: str = request.headers.get("Authorization", "")
        payload = None

        if authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
            # verify_access_token is synchronous
            payload = verify_access_token(token)

        # Set context variable for the duration of this request
        token_var = _auth_context.set(payload)
        try:
            response = await call_next(request)
            return response
        finally:
            _auth_context.reset(token_var)

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.security.jwt_handler import decode_access_token

IDLE_TIMEOUT = timedelta(minutes=30)
_last_seen: dict[str, datetime] = {}


class SessionTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                payload = decode_access_token(token)
                session_key = payload.get("jti") or payload.get("sub")
                now = datetime.now(timezone.utc)
                if session_key:
                    last_seen = _last_seen.get(session_key)
                    if last_seen and now - last_seen > IDLE_TIMEOUT:
                        _last_seen.pop(session_key, None)
                        return JSONResponse(
                            {"detail": "Session expired due to inactivity"},
                            status_code=401,
                        )
                    _last_seen[session_key] = now
            except Exception:
                pass

        return await call_next(request)

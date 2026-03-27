from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

AUTHENTICATED_RATE_LIMIT = "100/hour"
GUEST_RATE_LIMIT = "20/hour"


def rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        return auth_header
    return get_remote_address(request)


limiter = Limiter(
    key_func=rate_limit_key,
    enabled=os.getenv("WEAVER_DISABLE_RATE_LIMITS") != "1",
)

import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_real_ip(request: Request) -> str:
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return get_remote_address(request)

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0").replace("/0", "/1")
limiter = Limiter(key_func=get_real_ip, storage_uri=redis_url)
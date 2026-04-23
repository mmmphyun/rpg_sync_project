from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_real_ip(request: Request) -> str:
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_real_ip)
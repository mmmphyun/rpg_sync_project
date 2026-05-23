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

redis_url_env = os.getenv("REDIS_URL")

# REDIS_URL 환경 변수가 명시적으로 정의되지 않았거나, 
# 로컬 개발/테스트 환경에서 메모리 리미터 강제 옵션이 켜져 있다면 인메모리(memory://)로 폴백합니다.
is_docker = os.path.exists("/.dockerenv")
if not redis_url_env or os.getenv("USE_MEMORY_LIMITER") == "True":
    storage_uri = "memory://"
    print("[System] REDIS_URL이 정의되지 않았거나 오프라인 환경이므로 slowapi Limiter를 인메모리 스토리지(memory://)로 전환합니다.", flush=True)
elif "redis://redis" in redis_url_env and not is_docker:
    storage_uri = "memory://"
    print("[System] 로컬 수동 실행 환경이므로 slowapi Limiter를 인메모리 스토리지(memory://)로 전환합니다.", flush=True)
else:
    storage_uri = redis_url_env.replace("/0", "/1")

limiter = Limiter(key_func=get_real_ip, storage_uri=storage_uri)
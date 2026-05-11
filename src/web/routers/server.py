import time
from fastapi import APIRouter
from mcstatus import JavaServer

router = APIRouter(
    tags=["server"]
)

# 인메모리 캐시 저장소 (60초 TTL)
cache = {
    "data": None,
    "last_updated": 0
}

CACHE_TTL = 60  # 60초 동안은 MC 서버를 찌르지 않고 캐시된 데이터 반환
SERVER_ADDRESS = "fossil.playit.plus:25565"


@router.get("/status")
async def get_server_status():
    current_time = time.time()

    # 캐시가 존재하고 유효 시간이 지나지 않았다면 즉시 반환
    if cache["data"] and (current_time - cache["last_updated"] < CACHE_TTL):
        return cache["data"]

    try:
        # 캐시가 만료되었거나 없을 때만 MC 서버로 실제 비동기 핑 전송
        mc_server = await JavaServer.async_lookup(SERVER_ADDRESS)
        status = await mc_server.async_status()

        result = {
            "online": True,
            "players": {
                "online": status.players.online,
                "max": status.players.max
            }
        }
    except Exception as e:
        print(f"MC Server Status Error: {e}")
        # 서버가 닫혀있거나 응답이 없을 경우 오프라인 처리
        result = {
            "online": False,
            "players": {
                "online": 0,
                "max": 0
            }
        }

    # 성공이든 실패든 그 결과를 캐싱하고 시간 갱신
    cache["data"] = result
    cache["last_updated"] = current_time

    return result

@router.get("/test-error", include_in_schema=False)
async def test_webhook_error():
    """실무: 관제탑 웹훅 발송 테스트용 임시 엔드포인트"""
    raise Exception("[Test] FastAPI 서버 웹훅 모니터링 연동 테스트 에러입니다.")
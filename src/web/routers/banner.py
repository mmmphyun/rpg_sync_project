from fastapi import APIRouter, HTTPException
import asyncio
from src.database.banner import get_active_banners

router = APIRouter()

@router.get("/")
async def fetch_banners():
    """
    메인 페이지 배너 렌더링용 API
    """
    try:
        # 실무 적용: DB I/O로 인한 이벤트 루프 블로킹 방지
        banners = await asyncio.to_thread(get_active_banners)
        return {"banners": banners}
    except Exception as e:
        print(f"[API Error] GET /api/v1/banners: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
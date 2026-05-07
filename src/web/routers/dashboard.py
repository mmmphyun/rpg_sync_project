import asyncio
from fastapi import APIRouter, HTTPException
from src.database.cache import get_cache, set_cache
from src.database.banner import get_active_banners
from src.database.board import get_recent_posts_for_web, get_popup_event_for_web
from src.database.reviews import get_recent_reviews_for_web

router = APIRouter()


@router.get("/main")
async def get_main_dashboard_data():
    """
    메인 페이지용 통합 데이터 조회 API (Aggregated Cache 적용)
    """
    cache_key = "cache:main_page:all"

    cached_data = await get_cache(cache_key)
    if cached_data:
        return cached_data

    try:
        banners, posts, popup, reviews = await asyncio.gather(
            asyncio.to_thread(get_active_banners),
            asyncio.to_thread(get_recent_posts_for_web, 5),
            asyncio.to_thread(get_popup_event_for_web),
            asyncio.to_thread(get_recent_reviews_for_web, 2)
        )
    except Exception as e:
        print(f"[Dashboard API Error] {e}")
        raise HTTPException(status_code=500, detail="Dashboard Data Load Failed")

    data = {
        "banners": banners,
        "posts": posts,
        "popup": popup,
        "reviews": reviews
    }

    await set_cache(cache_key, data, ex=3600)

    return data
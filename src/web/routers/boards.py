import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from src.web.dependencies import get_admin_user
from src.database.board import get_notices_for_web, update_notice_type, update_notice_tag, delete_notice_logic,update_notice_title_by_id
from src.database.board import set_popup_event
from src.bot.utils.s3_client import delete_from_r2
from src.web.limiter import limiter
from src.web.routers.auth import get_current_user
from src.database.cache import get_cache, set_cache, delete_cache

router = APIRouter()

# --- helper ---
async def invalidate_board_caches():
    """게시판 내용 변경 시 메인 페이지 및 주요 게시판 캐시를 일괄 무효화합니다."""
    await delete_cache("cache:main_page:all")
    await delete_cache("cache:boards:notice:page:1:tag:None")
    await delete_cache("cache:boards:event:page:1:tag:None")

# --- router ---
@router.get("/{board_type}")
@limiter.limit("60/minute")
async def get_board_list(request: Request, board_type: str, page: int = Query(1, ge=1), tag: str = None):
    cache_key = f"cache:boards:{board_type}:page:{page}:tag:{tag}"

    cached_data = await get_cache(cache_key)
    if cached_data:
        return cached_data

    limit = 5
    offset = (page - 1) * limit
    notices = await asyncio.to_thread(get_notices_for_web, board_type=board_type, limit=limit, offset=offset,
                                      tag_filter=tag)

    response_data = {"notices": notices, "page": page}

    await set_cache(cache_key, response_data, ex=86400)

    return response_data

@router.patch("/{notice_id}/popup")
@limiter.limit("5/minute")
async def update_popup_status(request: Request, notice_id: int, user: dict = Depends(get_current_user)):
    """관리자 전용: 특정 이벤트를 팝업으로 지정"""
    if user.get("server_role") not in ("주인장", "STAFF"):
        raise HTTPException(status_code=403, detail="권한이 없습니다.")

    success = await asyncio.to_thread(set_popup_event, notice_id)
    if not success:
        raise HTTPException(status_code=500, detail="팝업 지정에 실패했습니다.")

    await invalidate_board_caches()
    return {"message": "팝업이 성공적으로 지정되었습니다."}

@router.put("/{notice_id}/type")
@limiter.limit("10/minute")
async def change_notice_type(request: Request, notice_id: int, target_type: str, admin: dict = Depends(get_admin_user)):
    affected = update_notice_type(notice_id, target_type)
    if affected == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    await invalidate_board_caches()
    return {"message": "success", "notice_id": notice_id}

@router.put("/{notice_id}/tag")
@limiter.limit("10/minute")
async def change_notice_tag(request: Request, notice_id: int, target_tag: str, admin: dict = Depends(get_admin_user)):
    affected = update_notice_tag(notice_id, target_tag)
    if affected == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    await invalidate_board_caches()
    return {"message": "success", "notice_id": notice_id}

@router.patch("/{notice_id}/title")
@limiter.limit("10/minute")
async def change_notice_title(request: Request, notice_id: int, title: str = Body(..., embed=True), admin: dict = Depends(get_admin_user)):
    safe_title = title.strip() if title else None

    if safe_title and len(safe_title) > 200:
        raise HTTPException(status_code=400, detail="제목은 200자를 초과할 수 없습니다.")

    affected = update_notice_title_by_id(notice_id, safe_title)
    if not affected:
        raise HTTPException(status_code=404, detail="게시글을 업데이트할 수 없습니다.")

    await invalidate_board_caches()
    return {"message": "success", "notice_id": notice_id}

@router.delete("/{notice_id}")
@limiter.limit("10/minute")
async def delete_notice(request: Request, notice_id: int, admin: dict = Depends(get_admin_user)):
    image_urls = delete_notice_logic(notice_id)
    for url in image_urls:
        delete_from_r2(url)

    await invalidate_board_caches()
    return {"message": "success", "notice_id": notice_id}
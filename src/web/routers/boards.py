import html

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from src.web.dependencies import get_admin_user
from src.database.board import get_notices_for_web, update_notice_type, update_notice_tag, delete_notice_logic, get_recent_posts_for_web, update_notice_title, update_notice_title_by_id
from src.bot.utils.s3_client import delete_from_r2
from src.web.limiter import limiter

router = APIRouter()

@router.get("/recent")
@limiter.limit("60/minute")
async def get_recent_boards(request: Request):
    """메인 페이지용 최신 게시글 5개 조회 (서버 상태 공지 제외)"""
    posts = get_recent_posts_for_web(limit=5)
    return posts

@router.get("/{board_type}")
@limiter.limit("60/minute")
async def get_board_list(request: Request, board_type: str, page: int = Query(1, ge=1), tag: str = None):
    limit = 5
    offset = (page - 1) * limit
    notices = get_notices_for_web(board_type=board_type, limit=limit, offset=offset, tag_filter=tag)
    return {"notices": notices, "page": page}

@router.put("/{notice_id}/type")
@limiter.limit("10/minute")
async def change_notice_type(request: Request, notice_id: int, target_type: str, admin: dict = Depends(get_admin_user)):
    affected = update_notice_type(notice_id, target_type)
    if affected == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return {"message": "success", "notice_id": notice_id}

@router.put("/{notice_id}/tag")
@limiter.limit("10/minute")
async def change_notice_tag(request: Request, notice_id: int, target_tag: str, admin: dict = Depends(get_admin_user)):
    affected = update_notice_tag(notice_id, target_tag)
    if affected == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return {"message": "success", "notice_id": notice_id}

@router.patch("/{notice_id}/title")
@limiter.limit("10/minute")
async def change_notice_title(request: Request, notice_id: int, title: str = Body(..., embed=True), admin: dict = Depends(get_admin_user)):
    safe_title = html.escape(title.strip()) if title else None

    if safe_title and len(safe_title) > 200:
        raise HTTPException(status_code=400, detail="제목은 200자를 초과할 수 없습니다.")

    affected = update_notice_title_by_id(notice_id, safe_title)
    if not affected:
        raise HTTPException(status_code=404, detail="게시글을 업데이트할 수 없습니다.")
    return {"message": "success", "notice_id": notice_id}

@router.delete("/{notice_id}")
@limiter.limit("10/minute")
async def delete_notice(request: Request, notice_id: int, admin: dict = Depends(get_admin_user)):
    image_urls = delete_notice_logic(notice_id)
    for url in image_urls:
        delete_from_r2(url)
    return {"message": "success", "notice_id": notice_id}
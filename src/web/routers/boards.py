from fastapi import APIRouter, Depends, HTTPException, Query
from src.web.dependencies import get_admin_user
from src.database.queries import get_notices_for_web, update_notice_type, update_notice_tag, delete_notice_logic, get_recent_posts_for_web
from src.bot.utils.s3_client import delete_from_r2

router = APIRouter()

@router.get("/recent")
async def get_recent_boards():
    """메인 페이지용 최신 게시글 5개 조회 (서버 상태 공지 제외)"""
    posts = get_recent_posts_for_web(limit=5)
    return posts

@router.get("/{board_type}")
async def get_board_list(board_type: str, page: int = Query(1, ge=1), tag: str = None):
    limit = 5
    offset = (page - 1) * limit
    notices = get_notices_for_web(board_type=board_type, limit=limit, offset=offset, tag_filter=tag)
    return {"notices": notices, "page": page}

@router.put("/{notice_id}/type")
async def change_notice_type(notice_id: int, target_type: str, admin: dict = Depends(get_admin_user)):
    affected = update_notice_type(notice_id, target_type)
    if affected == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return {"message": "success", "notice_id": notice_id}

@router.put("/{notice_id}/tag")
async def change_notice_tag(notice_id: int, target_tag: str, admin: dict = Depends(get_admin_user)):
    affected = update_notice_tag(notice_id, target_tag)
    if affected == 0:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return {"message": "success", "notice_id": notice_id}

@router.delete("/{notice_id}")
async def delete_notice(notice_id: int, admin: dict = Depends(get_admin_user)):
    image_urls = delete_notice_logic(notice_id)
    for url in image_urls:
        delete_from_r2(url)
    return {"message": "success", "notice_id": notice_id}
import json
from fastapi import APIRouter, Request, Query, Body, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from src.database.tip import get_tips_for_web, upsert_tip, get_tip_comments, create_tip_comment
from src.database.tip import get_tip_by_id, update_tip_by_id, delete_tip_by_id, get_comment_by_id, delete_comment_by_id
from src.web.limiter import limiter
from src.web.routers.auth import get_current_user

router = APIRouter()


@router.get("/")
@limiter.limit("60/minute")
async def get_tip_list(
        request: Request,
        category: str = Query("BUILD"),
        page: int = Query(1, ge=1)
):
    limit = 10
    offset = (page - 1) * limit
    tips = get_tips_for_web(category=category, limit=limit, offset=offset)

    return {"tips": tips, "page": page, "category": category}


@router.post("/")
@limiter.limit("5/minute")
async def create_qna_tip(
        request: Request,
        title: str = Body(...),
        content: str = Body(...),
        user: dict = Depends(get_current_user)
):
    # 권한 및 세션 검증
    if not user or not user.get("is_logged_in"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    safe_title = title.strip()
    safe_content = content.strip()

    if not safe_title or not safe_content:
        raise HTTPException(status_code=400, detail="Title and content are required.")

    # 실무 적용: 웹 작성 폼은 QNA 카테고리로 고정하고 discord_thread_id를 NULL(None) 처리
    tip_data = {
        'category': 'QNA',
        'title': safe_title,
        'content': safe_content,
        'image_urls': json.dumps([]),  # Phase 4 초기버전: 텍스트 기반 작성 우선
        'youtube_urls': json.dumps([]),
        'discord_thread_id': None,
        'author_id': str(user.get("discord_id"))
    }

    affected = upsert_tip(tip_data)
    if not affected:
        raise HTTPException(status_code=500, detail="Database insertion failed.")

    return {"message": "success"}


class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None


@router.get("/{tip_id}/comments")
@limiter.limit("60/minute")
async def get_comments(request: Request, tip_id: int):
    comments = get_tip_comments(tip_id)

    # 실무 적용: 프론트엔드 연산 부담을 줄이기 위해 백엔드에서 트리 구조화 O(N)
    comment_dict = {
        c['comment_id']: {**c, 'created_at': c['created_at'].strftime('%Y-%m-%d %H:%M:%S'), 'replies': []}
        for c in comments
    }
    tree = []

    for c in comments:
        if c['parent_comment_id']:
            parent = comment_dict.get(c['parent_comment_id'])
            if parent:
                parent['replies'].append(comment_dict[c['comment_id']])
        else:
            tree.append(comment_dict[c['comment_id']])

    return {"comments": tree}


@router.post("/{tip_id}/comments")
@limiter.limit("20/minute")
async def add_comment(
        request: Request,
        tip_id: int,
        payload: CommentCreate,
        user: dict = Depends(get_current_user)
):
    if not user or not user.get("is_logged_in"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    safe_content = payload.content.strip()
    if not safe_content:
        raise HTTPException(status_code=400, detail="Content is required.")

    comment_id = create_tip_comment(
        tip_id=tip_id,
        author_id=str(user.get("discord_id")),
        content=safe_content,
        parent_id=payload.parent_comment_id
    )

    if not comment_id:
        raise HTTPException(status_code=500, detail="Database insertion failed.")

    return {"message": "success", "comment_id": comment_id}


@router.patch("/{tip_id}")
async def edit_tip(
        tip_id: int,
        title: str = Body(..., embed=True),
        content: str = Body(..., embed=True),
        user: dict = Depends(get_current_user)
):
    tip = get_tip_by_id(tip_id)
    if not tip:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    # 권한 검증
    if tip['author_id'] != str(user.get("discord_id")) and user.get("server_role") != 'admin':
        raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")

    affected = update_tip_by_id(tip_id, title.strip(), content.strip())
    return {"message": "success"}


@router.delete("/{tip_id}")
async def remove_tip(tip_id: int, user: dict = Depends(get_current_user)):
    tip = get_tip_by_id(tip_id)
    if not tip:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    if tip['author_id'] != str(user.get("discord_id")) and user.get("server_role") != 'admin':
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")

    delete_tip_by_id(tip_id)
    return {"message": "success"}


@router.delete("/{tip_id}/comments/{comment_id}")
async def remove_comment(comment_id: int, user: dict = Depends(get_current_user)):
    comment = get_comment_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")

    if comment['author_id'] != str(user.get("discord_id")) and user.get("server_role") != 'admin':
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")

    delete_comment_by_id(comment_id)
    return {"message": "success"}
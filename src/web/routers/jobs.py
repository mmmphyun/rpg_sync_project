import os
import psycopg2
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor
from src.web.dependencies import get_required_user
from src.database.queries import get_recent_reviews_for_web
from src.web.main import limiter

router = APIRouter()

class ReviewPayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., max_length=255)

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    return psycopg2.connect(db_url)

@router.get("/reviews/recent")
@limiter.limit("60/minute")
async def get_recent_reviews(request: Request):
    """메인 페이지용 최근 직업 평가 3개 조회"""
    reviews = get_recent_reviews_for_web(limit=3)
    return reviews

@router.get("/{job_id}/reviews")
@limiter.limit("60/minute")
def get_job_reviews(request: Request, job_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT 
                r.rating, 
                r.comment, 
                r.created_at, 
                u.nickname, 
                COALESCE(j.display_name, '직업 없음') AS job_name
            FROM job_reviews r
            JOIN users u ON r.discord_id = u.discord_id
            LEFT JOIN jobs j ON u.current_job_id = j.job_id
            WHERE r.job_id = %s
            ORDER BY r.created_at DESC
        """, (job_id,))
        reviews = cursor.fetchall()

        cursor.execute("SELECT COALESCE(ROUND(AVG(rating), 1), 0) as avg_rating FROM job_reviews WHERE job_id = %s",
                       (job_id,))
        avg_rating = cursor.fetchone()['avg_rating']

        return {"avg_rating": avg_rating, "reviews": reviews}
    finally:
        cursor.close()
        conn.close()

@router.post("/{job_id}/reviews", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def upsert_job_review(request: Request, job_id: int, payload: ReviewPayload, user: dict = Depends(get_required_user)):
    discord_id = user.get("sub")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO job_reviews (job_id, discord_id, rating, comment)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (job_id, discord_id) 
            DO UPDATE SET 
                rating = EXCLUDED.rating, 
                comment = EXCLUDED.comment, 
                updated_at = CURRENT_TIMESTAMP
        """, (job_id, discord_id, payload.rating, payload.comment))
        conn.commit()
        return {"message": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
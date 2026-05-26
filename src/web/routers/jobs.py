import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from src.web.dependencies import get_required_user
from src.database.reviews import get_job_reviews_data, upsert_job_review_db
from src.web.limiter import limiter

router = APIRouter()

class ReviewPayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., max_length=255)

@router.get("/{job_id}/reviews")
@limiter.limit("60/minute")
def get_job_reviews(request: Request, job_id: int):
    try:
        return get_job_reviews_data(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/reviews", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def upsert_job_review(request: Request, job_id: int, payload: ReviewPayload, user: dict = Depends(get_required_user)):
    discord_id = user.get("sub")
    try:
        return upsert_job_review_db(job_id, discord_id, payload.rating, payload.comment)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
Feedback API routes.
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import Feedback, get_db

router = APIRouter()
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")


class FeedbackRequest(BaseModel):
    feedback_type: str = Field(default="general", max_length=50)
    message: str = Field(..., min_length=2, max_length=2000)
    contact: Optional[str] = Field(default=None, max_length=200)
    page: Optional[str] = Field(default=None, max_length=500)
    user_agent: Optional[str] = Field(default=None, max_length=500)


def require_admin(x_admin_key: Optional[str] = Header(default=None)):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API is disabled")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@router.post("/feedback")
def create_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    item = Feedback(
        feedback_type=payload.feedback_type.strip() or "general",
        message=payload.message.strip(),
        contact=(payload.contact or "").strip() or None,
        page=(payload.page or "").strip() or None,
        user_agent=(payload.user_agent or "").strip() or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"ok": True, "id": item.id}


@router.get("/feedback")
def list_feedback(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    rows = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(limit).all()
    return {
        "feedback": [
            {
                "id": row.id,
                "feedback_type": row.feedback_type,
                "message": row.message,
                "contact": row.contact,
                "page": row.page,
                "user_agent": row.user_agent,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.campaigns.schemas import PostUpdate, PostResponse
from app.modules.campaigns.service import CampaignService
from app.dependencies import get_current_agency_id

router = APIRouter(prefix="/posts", tags=["posts"])


@router.put("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: str,
    data: PostUpdate,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Update post title and/or content. Sets status to edited. Locked after plan approval."""
    return CampaignService.update_post(
        db,
        post_id,
        agency_id,
        title=data.title,
        content=data.content,
    )

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignDetailResponse,
    PostResponse,
    GetPlanResponse,
    GeneratePlanRequest,
    GeneratePlanResponse,
)
from app.modules.campaigns.service import CampaignService
from app.dependencies import get_current_user, get_current_agency_id
from app.modules.auth.models import User

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    campaign_data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    agency_id: str = Depends(get_current_agency_id),
):
    """Create a new campaign for a client."""
    return CampaignService.create_campaign(
        db, campaign_data, agency_id, current_user.id
    )


@router.get("", response_model=List[CampaignResponse])
def get_campaigns(
    client_id: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get campaigns for the current agency, optionally filtered by client."""
    return CampaignService.get_campaigns(db, agency_id, client_id=client_id, skip=skip, limit=limit)


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get a campaign with agency and client names."""
    campaign, agency_name, client_name = CampaignService.get_campaign_with_names(
        db, campaign_id, agency_id
    )
    return CampaignDetailResponse(
        **CampaignResponse.model_validate(campaign).model_dump(),
        agency_name=agency_name,
        client_name=client_name,
    )


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    campaign_data: CampaignUpdate,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Update a campaign."""
    return CampaignService.update_campaign(db, campaign_id, agency_id, campaign_data)


@router.get("/{campaign_id}/plan", response_model=GetPlanResponse)
def get_plan(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get the monthly plan for a campaign (plan is null if none exists yet)."""
    return CampaignService.get_plan(db, campaign_id, agency_id)


@router.post("/{campaign_id}/generate-plan", response_model=GeneratePlanResponse)
def generate_plan(
    campaign_id: str,
    body: Optional[GeneratePlanRequest] = Body(None),
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Generate or regenerate AI monthly plan (4 weeks, configurable posts per week/channels). Optional body for generation options."""
    return CampaignService.generate_plan(db, campaign_id, agency_id, body)


@router.post("/{campaign_id}/approve-plan", response_model=CampaignResponse)
def approve_plan(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Approve the monthly plan; all posts marked approved and editing locked."""
    return CampaignService.approve_plan(db, campaign_id, agency_id)


@router.post("/{campaign_id}/reset-plan", response_model=CampaignResponse)
def reset_plan(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Remove the current planning and generated posts; campaign returns to draft so user can generate again."""
    return CampaignService.reset_plan(db, campaign_id, agency_id)


@router.get("/{campaign_id}/posts", response_model=List[PostResponse])
def get_campaign_posts(
    campaign_id: str,
    db: Session = Depends(get_db),
    agency_id: str = Depends(get_current_agency_id),
):
    """Get all posts for a campaign (grouped by week in service)."""
    posts = CampaignService.get_posts_by_campaign(db, campaign_id, agency_id)
    return [PostResponse.model_validate(p) for p in posts]


# Legacy endpoints (optional): generate-posts, approve-post - can be removed or kept for backward compat

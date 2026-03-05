from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.modules.campaigns.models import CampaignStatus, PostStatus


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    language: str = Field(default="es", pattern="^(es|en)$")


class CampaignCreate(CampaignBase):
    client_id: str


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None


class CampaignResponse(CampaignBase):
    id: str
    client_id: str
    status: CampaignStatus
    ai_plan: Optional[Dict[str, Any]] = None
    approved_at: Optional[datetime] = None
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignDetailResponse(CampaignResponse):
    """Campaign with agency and client names for detail view."""
    agency_name: Optional[str] = None
    client_name: Optional[str] = None


class PostBase(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    platform: Optional[str] = None
    scheduled_at: Optional[datetime] = None


class PostCreate(PostBase):
    campaign_id: str


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    status: Optional[PostStatus] = None
    scheduled_at: Optional[datetime] = None


class PostResponse(PostBase):
    id: str
    monthly_plan_id: str
    week_number: int
    status: PostStatus
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    published_post_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalCreate(BaseModel):
    campaign_id: str
    post_id: Optional[str] = None
    approval_type: str = Field(..., pattern="^(plan_approval|post_approval)$")
    approved: bool
    comments: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    campaign_id: str
    post_id: Optional[str] = None
    approval_type: str
    approved: bool
    comments: Optional[str] = None
    approved_by: str
    created_at: datetime

    class Config:
        from_attributes = True

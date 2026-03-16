from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.modules.campaigns.models import CampaignStatus, PostStatus

# Allowed values for generate-plan request
ALLOWED_CHANNELS = frozenset({"linkedin", "instagram"})
ALLOWED_DISTRIBUTION_STRATEGIES = frozenset({"balanced", "linkedin_priority", "instagram_priority"})
ALLOWED_CONTENT_LENGTHS = frozenset({"short", "medium", "long"})
ALLOWED_CAMPAIGN_GOALS = frozenset({
    "awareness", "engagement", "leads", "sales", "brand_loyalty",
    "traffic", "conversions", "community", "thought_leadership",
})


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


# --- Monthly plan (get plan / generate plan) ---
# MonthlyPlanPost: slim post shape when nested inside a plan (no monthly_plan_id, timestamps, etc.).
# PostResponse is the full post; nothing in schemas.py previously did this nested shape.
class MonthlyPlanPost(BaseModel):
    id: str
    week_number: int
    title: Optional[str] = None
    content: str
    platform: Optional[str] = None
    status: PostStatus


# Stored generation config (audit/debugging). Shape: posts_per_week, channels, distribution_strategy,
# campaign_goal_mix, content_variation, language, content_length, call_to_action_required.
# Returned as optional dict in MonthlyPlanResponse.
# MonthlyPlanResponse: a plan with its posts and optional generation config.
class MonthlyPlanResponse(BaseModel):
    id: str
    campaign_id: str
    posts: List[MonthlyPlanPost]
    created_at: datetime
    updated_at: Optional[datetime] = None
    generation_config: Optional[Dict[str, Any]] = None


# GeneratePlanRequest: optional body for POST generate-plan. All fields optional; defaults applied.
class GeneratePlanRequest(BaseModel):
    posts_per_week: Optional[int] = Field(None, ge=3, le=7, description="Posts per week (3-7)")
    channels: Optional[List[str]] = Field(None, description="Platforms: linkedin, instagram, or both")
    distribution_strategy: Optional[str] = Field(
        None, description="balanced | linkedin_priority | instagram_priority"
    )
    campaign_goal_mix: Optional[List[str]] = Field(None, description="Marketing goals for content mix")
    content_variation: Optional[bool] = Field(None, description="Vary content types/themes")
    language: Optional[str] = Field(None, pattern="^(es|en)$", description="Content language")
    content_length: Optional[str] = Field(None, description="short | medium | long")
    call_to_action_required: Optional[bool] = Field(None, description="Include CTA in posts")

    @field_validator("channels")
    @classmethod
    def channels_must_be_linkedin_or_instagram(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if not v:
            raise ValueError("channels must contain at least one of: linkedin, instagram")
        allowed = {c.lower() for c in v}
        if not allowed.issubset(ALLOWED_CHANNELS):
            raise ValueError("channels may only contain: linkedin, instagram")
        return list(dict.fromkeys([c.lower() for c in v]))  # unique, preserve order

    @field_validator("distribution_strategy")
    @classmethod
    def distribution_strategy_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.lower() not in ALLOWED_DISTRIBUTION_STRATEGIES:
            raise ValueError(
                "distribution_strategy must be one of: balanced, linkedin_priority, instagram_priority"
            )
        return v.lower()

    @field_validator("campaign_goal_mix")
    @classmethod
    def campaign_goals_allowed(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None or not v:
            return v
        lower = [g.lower() for g in v]
        invalid = set(lower) - ALLOWED_CAMPAIGN_GOALS
        if invalid:
            raise ValueError(
                f"campaign_goal_mix contains invalid goals: {invalid}. "
                f"Allowed: {sorted(ALLOWED_CAMPAIGN_GOALS)}"
            )
        return list(dict.fromkeys(lower))

    @field_validator("content_length")
    @classmethod
    def content_length_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.lower() not in ALLOWED_CONTENT_LENGTHS:
            raise ValueError("content_length must be one of: short, medium, long")
        return v.lower()


# Resolved generation options (all required) after merging request with campaign defaults.
class GenerationOptions(BaseModel):
    posts_per_week: int = Field(..., ge=3, le=7)
    channels: List[str] = Field(..., min_length=1)
    distribution_strategy: str = Field(...)
    campaign_goal_mix: List[str] = Field(default_factory=list)
    content_variation: bool = True
    language: str = Field(..., pattern="^(es|en)$")
    content_length: str = Field(...)
    call_to_action_required: bool = False

    class Config:
        frozen = True


def resolve_generation_options(
    request: Optional[GeneratePlanRequest],
    campaign_language: str,
) -> GenerationOptions:
    """Merge optional request with defaults. Campaign language used when request.language is None."""
    r = request
    return GenerationOptions(
        posts_per_week=r.posts_per_week if r and r.posts_per_week is not None else 4,
        channels=(
            r.channels
            if r and r.channels is not None and len(r.channels) > 0
            else ["linkedin", "instagram"]
        ),
        distribution_strategy=(
            r.distribution_strategy
            if r and r.distribution_strategy is not None
            else "balanced"
        ),
        campaign_goal_mix=(
            r.campaign_goal_mix
            if r and r.campaign_goal_mix is not None
            else ["awareness", "engagement"]
        ),
        content_variation=(
            r.content_variation if r and r.content_variation is not None else True
        ),
        language=(
            r.language if r and r.language is not None else campaign_language
        ),
        content_length=(
            r.content_length if r and r.content_length is not None else "medium"
        ),
        call_to_action_required=(
            r.call_to_action_required if r and r.call_to_action_required is not None else False
        ),
    )


# GetPlanResponse: used when returning current plan (plan may be null). Not in schemas before.
class GetPlanResponse(BaseModel):
    plan: Optional[MonthlyPlanResponse] = None


# GeneratePlanResponse: response of generate-plan endpoint (campaign + new plan + mode).
class GeneratePlanResponse(BaseModel):
    campaign: CampaignResponse
    plan: MonthlyPlanResponse
    generation_mode: str

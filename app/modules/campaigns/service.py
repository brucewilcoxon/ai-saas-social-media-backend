from sqlalchemy.orm import Session
from app.modules.campaigns.models import (
    Campaign,
    Post,
    MonthlyPlan,
    CampaignStatus,
    PostStatus,
)
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    MonthlyPlanResponse,
    MonthlyPlanPost,
    GeneratePlanResponse,
)
from app.modules.ai.service import AIService, validate_content_language
from app.modules.clients.models import Client
from app.modules.agencies.models import Agency
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime, timezone


def _ensure_client_in_agency(db: Session, client_id: str, agency_id: str) -> Client:
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.agency_id == agency_id,
    ).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or does not belong to your agency",
        )
    return client


class CampaignService:
    @staticmethod
    def get_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> "GetPlanResponse":
        """
        Return the existing monthly plan (if any) for a campaign.
        If no plan exists yet, returns plan=null to match frontend's GetPlanResponse.
        """
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        # Assume at most one monthly plan per campaign.
        plan = (
            db.query(MonthlyPlan)
            .filter(MonthlyPlan.campaign_id == campaign.id)
            .first()
        )
        if not plan:
            from app.modules.campaigns.schemas import GetPlanResponse  # local import to avoid cycle

            return GetPlanResponse(plan=None)

        posts = sorted(plan.posts, key=lambda p: (p.week_number, p.id))
        from app.modules.campaigns.schemas import MonthlyPlanPost, MonthlyPlanResponse, GetPlanResponse  # local import

        plan_schema = MonthlyPlanResponse(
            id=plan.id,
            campaign_id=plan.campaign_id,
            posts=[
                MonthlyPlanPost(
                    id=p.id,
                    week_number=p.week_number,
                    title=p.title,
                    content=p.content,
                    platform=p.platform,
                    status=p.status,
                )
                for p in posts
            ],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
        return GetPlanResponse(plan=plan_schema)

    @staticmethod
    def create_campaign(
        db: Session,
        campaign_data: CampaignCreate,
        agency_id: str,
        user_id: str,
    ) -> Campaign:
        _ensure_client_in_agency(db, campaign_data.client_id, agency_id)
        campaign = Campaign(
            name=campaign_data.name,
            description=campaign_data.description,
            language=campaign_data.language,
            client_id=campaign_data.client_id,
            created_by=user_id,
            status=CampaignStatus.DRAFT,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def get_campaigns(
        db: Session,
        agency_id: str,
        client_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Campaign]:
        q = db.query(Campaign).join(Client).filter(Client.agency_id == agency_id)
        if client_id:
            q = q.filter(Campaign.client_id == client_id)
        return q.offset(skip).limit(limit).all()

    @staticmethod
    def get_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
        with_names: bool = False,
    ) -> Campaign:
        campaign = (
            db.query(Campaign)
            .join(Client)
            .filter(
                Campaign.id == campaign_id,
                Client.agency_id == agency_id,
            )
            .first()
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found",
            )
        return campaign

    @staticmethod
    def get_campaign_with_names(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> tuple[Campaign, str, str]:
        campaign = (
            db.query(Campaign, Agency.name.label("agency_name"), Client.name.label("client_name"))
            .join(Client, Campaign.client_id == Client.id)
            .join(Agency, Client.agency_id == Agency.id)
            .filter(Campaign.id == campaign_id, Client.agency_id == agency_id)
            .first()
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found",
            )
        c, agency_name, client_name = campaign
        return c, agency_name or "", client_name or ""

    @staticmethod
    def update_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
        campaign_data: CampaignUpdate,
    ) -> Campaign:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        update_data = campaign_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def generate_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> GeneratePlanResponse:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status != CampaignStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must be in draft status to generate a plan",
            )
        try:
            raw_posts = AIService.generate_monthly_plan_posts(
                campaign_name=campaign.name,
                description=campaign.description or "",
                language=campaign.language,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        for p in raw_posts:
            validate_content_language(p.get("content", ""), campaign.language)
        plan = MonthlyPlan(campaign_id=campaign.id)
        db.add(plan)
        db.flush()
        # Resolve tenant_id for posts via campaign -> client -> agency.
        tenant_id = campaign.client.agency.tenant_id  # type: ignore[assignment]
        for p in raw_posts:
            post = Post(
                tenant_id=tenant_id,
                monthly_plan_id=plan.id,
                week_number=p.get("week_number", 1),
                title=p.get("title"),
                content=p.get("content", ""),
                platform=p.get("platform"),
                status=PostStatus.GENERATED,
            )
            db.add(post)
        campaign.status = CampaignStatus.PLANNING_GENERATED
        db.commit()
        db.refresh(campaign)
        db.refresh(plan)
        plan_posts = sorted(plan.posts, key=lambda p: (p.week_number, p.id))
        campaign_schema = CampaignResponse.model_validate(campaign)
        plan_schema = MonthlyPlanResponse(
            id=plan.id,
            campaign_id=plan.campaign_id,
            posts=[
                MonthlyPlanPost(
                    id=p.id,
                    week_number=p.week_number,
                    title=p.title,
                    content=p.content,
                    platform=p.platform,
                    status=p.status,
                )
                for p in plan_posts
            ],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
        # Backend currently always uses mock generator (see AIService.generate_monthly_plan_posts).
        return GeneratePlanResponse(
            campaign=campaign_schema,
            plan=plan_schema,
            generation_mode="mock",
        )

    @staticmethod
    def approve_plan(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> Campaign:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        if campaign.status != CampaignStatus.PLANNING_GENERATED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign must have a generated plan to approve",
            )
        now = datetime.now(timezone.utc)
        campaign.status = CampaignStatus.PLANNING_APPROVED
        campaign.approved_at = now
        for plan in campaign.monthly_plans:
            for post in plan.posts:
                post.status = PostStatus.APPROVED
                post.approved_at = now
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def get_posts_by_campaign(
        db: Session,
        campaign_id: str,
        agency_id: str,
    ) -> List[Post]:
        campaign = CampaignService.get_campaign(db, campaign_id, agency_id)
        out = []
        for plan in campaign.monthly_plans:
            for post in plan.posts:
                out.append(post)
        return sorted(out, key=lambda p: (p.week_number, p.id))

    @staticmethod
    def update_post(
        db: Session,
        post_id: str,
        agency_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Post:
        post = (
            db.query(Post)
            .join(MonthlyPlan)
            .join(Campaign)
            .join(Client)
            .filter(
                Post.id == post_id,
                Client.agency_id == agency_id,
            )
            .first()
        )
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )
        campaign = post.monthly_plan.campaign
        if campaign.status == CampaignStatus.PLANNING_APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Editing is locked after plan approval",
            )
        if title is not None:
            post.title = title
        if content is not None:
            post.content = content
        post.status = PostStatus.EDITED
        db.commit()
        db.refresh(post)
        return post

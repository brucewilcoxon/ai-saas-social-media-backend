from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Boolean, JSON, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR
import enum
import uuid
from app.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    PLANNING_GENERATED = "planning_generated"
    PLANNING_EDITING = "planning_editing"
    PLANNING_APPROVED = "planning_approved"
    # Legacy / future
    POSTS_GENERATED = "posts_generated"
    POSTS_APPROVED = "posts_approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    PENDING_APPROVAL = "pending_approval"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(CHAR(36), ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    language = Column(String(10), default="es", nullable=False)  # es or en
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False)
    ai_plan = Column(JSON)  # legacy / optional
    approved_at = Column(DateTime(timezone=True), nullable=True)  # set when plan approved
    created_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("Client", back_populates="campaigns")
    monthly_plans = relationship(
        "MonthlyPlan", back_populates="campaign", cascade="all, delete-orphan"
    )


class MonthlyPlan(Base):
    """One plan per campaign (4 weeks). Stores generation config used for audit/debugging."""

    __tablename__ = "monthly_plans"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    generation_config = Column(JSON, nullable=True)  # config used to generate this plan (posts_per_week, channels, etc.)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    campaign = relationship("Campaign", back_populates="monthly_plans")
    posts = relationship(
        "Post", back_populates="monthly_plan", cascade="all, delete-orphan"
    )


class Post(Base):
    __tablename__ = "posts"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(
        CHAR(36), ForeignKey("campaigns.id"), nullable=True, index=True
    )
    monthly_plan_id = Column(
        CHAR(36), ForeignKey("monthly_plans.id"), nullable=False, index=True
    )
    week_number = Column(Integer, nullable=False)  # 1-4
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    status = Column(Enum(PostStatus), default=PostStatus.GENERATED, nullable=False)
    platform = Column(String(50))  # linkedin, instagram
    approved_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    published_post_id = Column(String(255))
    extra_data = Column("metadata", JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    monthly_plan = relationship("MonthlyPlan", back_populates="posts")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, index=True)
    campaign_id = Column(CHAR(36), ForeignKey("campaigns.id"), nullable=False, index=True)
    post_id = Column(CHAR(36), ForeignKey("posts.id"), nullable=True)
    approval_type = Column(String(50), nullable=False)
    approved_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    approved = Column(Boolean, nullable=False)
    comments = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

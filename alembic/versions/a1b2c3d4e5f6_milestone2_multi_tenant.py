"""Milestone 2: Multi-tenant structure (Agency, Client, MonthlyPlan, Post)

Revision ID: a1b2c3d4e5f6
Revises: 72146d1208a5
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "a1b2c3d4e5f6"
down_revision = "72146d1208a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create agencies table
    op.create_table(
        "agencies",
        sa.Column("id", mysql.CHAR(length=36), nullable=False),
        sa.Column("tenant_id", mysql.CHAR(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_agencies_id"), "agencies", ["id"], unique=False)
    op.create_index(op.f("ix_agencies_tenant_id"), "agencies", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_agencies_slug"), "agencies", ["slug"], unique=True)

    # 2. Create clients table
    op.create_table(
        "clients",
        sa.Column("id", mysql.CHAR(length=36), nullable=False),
        sa.Column("agency_id", mysql.CHAR(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_clients_id"), "clients", ["id"], unique=False)
    op.create_index(op.f("ix_clients_agency_id"), "clients", ["agency_id"], unique=False)

    # 3. Add agency_id to users
    op.add_column("users", sa.Column("agency_id", mysql.CHAR(length=36), nullable=True))
    op.create_foreign_key(
        "fk_users_agency_id", "users", "agencies", ["agency_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index(op.f("ix_users_agency_id"), "users", ["agency_id"], unique=False)

    # 4. Add client_id and approved_at to campaigns
    op.add_column("campaigns", sa.Column("client_id", mysql.CHAR(length=36), nullable=True))
    op.add_column(
        "campaigns",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_campaigns_client_id", "campaigns", "clients", ["client_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index(op.f("ix_campaigns_client_id"), "campaigns", ["client_id"], unique=False)

    # 5. Create monthly_plans table
    op.create_table(
        "monthly_plans",
        sa.Column("id", mysql.CHAR(length=36), nullable=False),
        sa.Column("campaign_id", mysql.CHAR(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_monthly_plans_id"), "monthly_plans", ["id"], unique=False)
    op.create_index(
        op.f("ix_monthly_plans_campaign_id"),
        "monthly_plans",
        ["campaign_id"],
        unique=False,
    )

    # 6. Add new columns to posts (monthly_plan_id, week_number, title, approved_at)
    op.add_column(
        "posts",
        sa.Column("monthly_plan_id", mysql.CHAR(length=36), nullable=True),
    )
    op.add_column("posts", sa.Column("week_number", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("title", sa.String(length=500), nullable=True))
    op.add_column(
        "posts",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_posts_monthly_plan_id",
        "posts",
        "monthly_plans",
        ["monthly_plan_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_posts_monthly_plan_id"),
        "posts",
        ["monthly_plan_id"],
        unique=False,
    )

    # 7. Data migration: one agency per tenant, one client per agency, link users and campaigns
    conn = op.get_bind()
    # Create one agency per tenant
    conn.execute(
        sa.text("""
            INSERT INTO agencies (id, tenant_id, name, slug, is_active)
            SELECT UUID(), id, name, slug, 1 FROM tenants
        """)
    )
    # Set user.agency_id from tenant
    conn.execute(
        sa.text("""
            UPDATE users u
            INNER JOIN agencies a ON a.tenant_id = u.tenant_id
            SET u.agency_id = a.id
        """)
    )
    # Create one client per agency
    conn.execute(
        sa.text("""
            INSERT INTO clients (id, agency_id, name, is_active)
            SELECT UUID(), id, CONCAT(name, ' - Default Client'), 1 FROM agencies
        """)
    )
    # Set campaign.client_id from tenant (one client per agency)
    conn.execute(
        sa.text("""
            UPDATE campaigns c
            INNER JOIN agencies a ON a.tenant_id = c.tenant_id
            INNER JOIN clients cl ON cl.agency_id = a.id
            SET c.client_id = cl.id
        """)
    )
    # Create one monthly_plan per campaign and link existing posts
    conn.execute(
        sa.text("""
            INSERT INTO monthly_plans (id, campaign_id)
            SELECT UUID(), id FROM campaigns
        """)
    )
    # Link posts to monthly_plan and set week_number
    conn.execute(
        sa.text("""
            UPDATE posts p
            INNER JOIN monthly_plans mp ON mp.campaign_id = p.campaign_id
            SET p.monthly_plan_id = mp.id, p.week_number = 1
        """)
    )

    # 8. Make client_id and agency_id non-null
    op.alter_column(
        "campaigns",
        "client_id",
        existing_type=mysql.CHAR(length=36),
        nullable=False,
    )
    op.alter_column(
        "users",
        "agency_id",
        existing_type=mysql.CHAR(length=36),
        nullable=False,
    )

    # 9. Drop tenant_id from campaigns (FK dropped with column)
    op.drop_index(op.f("ix_campaigns_tenant_id"), table_name="campaigns")
    op.drop_column("campaigns", "tenant_id")

    # 10. Make posts.monthly_plan_id and week_number non-null (posts that have monthly_plan_id set)
    op.alter_column(
        "posts",
        "monthly_plan_id",
        existing_type=mysql.CHAR(length=36),
        nullable=False,
    )
    op.alter_column(
        "posts",
        "week_number",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="1",
    )

    # 11. Drop campaign_id from posts (post belongs to monthly_plan only; FK dropped with column)
    op.drop_index(op.f("ix_posts_campaign_id"), table_name="posts")
    op.drop_column("posts", "campaign_id")

    # 12. Add new enum values for campaign status (MySQL)
    op.execute(
        "ALTER TABLE campaigns MODIFY COLUMN status ENUM("
        "'DRAFT','AI_PLAN_CREATED','PLAN_APPROVED','PLANNING_GENERATED','PLANNING_APPROVED',"
        "'POSTS_GENERATED','POSTS_APPROVED','SCHEDULED','PUBLISHING','COMPLETED','CANCELLED')"
    )
    # Add new enum values for post status
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'DRAFT','GENERATED','EDITED','APPROVED','PENDING_APPROVAL',"
        "'SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )


def downgrade() -> None:
    # Restore tenant_id to campaigns (recreate column and backfill from client.agency.tenant_id)
    op.add_column(
        "campaigns",
        sa.Column("tenant_id", mysql.CHAR(length=36), nullable=True),
    )
    op.create_foreign_key(
        "campaigns_ibfk_2", "campaigns", "tenants", ["tenant_id"], ["id"]
    )
    op.create_index(op.f("ix_campaigns_tenant_id"), "campaigns", ["tenant_id"], unique=False)
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE campaigns c
            INNER JOIN clients cl ON cl.id = c.client_id
            INNER JOIN agencies a ON a.id = cl.agency_id
            SET c.tenant_id = a.tenant_id
        """)
    )
    op.alter_column("campaigns", "tenant_id", nullable=False)

    op.drop_constraint("fk_campaigns_client_id", "campaigns", type_="foreignkey")
    op.drop_index(op.f("ix_campaigns_client_id"), table_name="campaigns")
    op.drop_column("campaigns", "client_id")
    op.drop_column("campaigns", "approved_at")

    # Restore campaign_id on posts from monthly_plan before dropping
    op.add_column("posts", sa.Column("campaign_id", mysql.CHAR(length=36), nullable=True))
    conn.execute(
        sa.text("""
            UPDATE posts p
            INNER JOIN monthly_plans mp ON mp.id = p.monthly_plan_id
            SET p.campaign_id = mp.campaign_id
        """)
    )
    op.alter_column("posts", "campaign_id", nullable=False)
    op.create_foreign_key("posts_ibfk_1", "posts", "campaigns", ["campaign_id"], ["id"])
    op.create_index(op.f("ix_posts_campaign_id"), "posts", ["campaign_id"], unique=False)

    op.drop_constraint("fk_posts_monthly_plan_id", "posts", type_="foreignkey")
    op.drop_index(op.f("ix_posts_monthly_plan_id"), table_name="posts")
    op.drop_column("posts", "monthly_plan_id")
    op.drop_column("posts", "week_number")
    op.drop_column("posts", "title")
    op.drop_column("posts", "approved_at")

    op.drop_table("monthly_plans")

    op.drop_constraint("fk_users_agency_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_agency_id"), table_name="users")
    op.drop_column("users", "agency_id")

    op.drop_table("clients")
    op.drop_index(op.f("ix_agencies_slug"), table_name="agencies")
    op.drop_index(op.f("ix_agencies_tenant_id"), table_name="agencies")
    op.drop_index(op.f("ix_agencies_id"), table_name="agencies")
    op.drop_table("agencies")

    # Restore original enums
    op.execute(
        "ALTER TABLE campaigns MODIFY COLUMN status ENUM("
        "'DRAFT','AI_PLAN_CREATED','PLAN_APPROVED','POSTS_GENERATED','POSTS_APPROVED',"
        "'SCHEDULED','PUBLISHING','COMPLETED','CANCELLED')"
    )
    op.execute(
        "ALTER TABLE posts MODIFY COLUMN status ENUM("
        "'DRAFT','PENDING_APPROVAL','APPROVED','SCHEDULED','PUBLISHED','FAILED','CANCELLED')"
    )

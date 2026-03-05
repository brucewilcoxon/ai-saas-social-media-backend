from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app.config import settings
# Import all models for Alembic autogenerate
from app.modules.auth.models import User
from app.modules.tenants.models import Tenant
from app.modules.agencies.models import Agency
from app.modules.clients.models import Client
from app.modules.campaigns.models import Campaign, Post, MonthlyPlan, Approval
from app.modules.social.models import SocialAccount
from app.modules.stripe.models import Subscription
from app.modules.scheduler.models import ScheduledPost

# this is the Alembic Config object
config = context.config

# Note: We use settings.DATABASE_URL directly in migration functions
# to avoid ConfigParser interpolation issues with URL-encoded passwords

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Use database URL directly to avoid ConfigParser interpolation issues
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Use database URL directly to avoid ConfigParser interpolation issues
    from sqlalchemy import create_engine
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

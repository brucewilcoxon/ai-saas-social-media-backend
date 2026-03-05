from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import CHAR
import uuid
from app.database import Base


class Agency(Base):
    __tablename__ = "agencies"

    id = Column(CHAR(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=True, index=True)  # backward compat
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    users = relationship("User", back_populates="agency")
    clients = relationship("Client", back_populates="agency", cascade="all, delete-orphan")

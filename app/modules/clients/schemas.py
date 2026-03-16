from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ClientUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ClientResponse(BaseModel):
    id: str
    agency_id: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

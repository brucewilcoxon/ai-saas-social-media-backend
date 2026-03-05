from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AgencyResponse(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

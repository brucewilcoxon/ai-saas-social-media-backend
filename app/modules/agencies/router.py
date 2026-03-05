from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.modules.agencies.schemas import AgencyResponse
from app.modules.agencies.service import AgencyService
from app.dependencies import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/agencies", tags=["agencies"])


@router.get("/me", response_model=AgencyResponse)
def get_my_agency(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's agency."""
    return AgencyService.get_agency_for_user(current_user, db)

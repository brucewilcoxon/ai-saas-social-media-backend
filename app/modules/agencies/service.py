from sqlalchemy.orm import Session
from app.modules.auth.models import User
from app.modules.agencies.models import Agency
from fastapi import HTTPException, status


class AgencyService:
    @staticmethod
    def get_agency_for_user(user: User, db: Session) -> Agency:
        """Get the agency for the current user."""
        if user.agency_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User has no agency assigned",
            )
        agency = db.query(Agency).filter(Agency.id == user.agency_id).first()
        if not agency:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agency not found",
            )
        return agency

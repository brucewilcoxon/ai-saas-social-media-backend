from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.modules.clients.schemas import ClientCreate, ClientUpdate, ClientResponse
from app.modules.clients.service import ClientService
from app.modules.agencies.service import AgencyService
from app.dependencies import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=List[ClientResponse])
def list_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List clients for the current user's agency."""
    agency = AgencyService.get_agency_for_user(current_user, db)
    return ClientService.list_by_agency(db, agency.id)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a client under the current user's agency."""
    agency = AgencyService.get_agency_for_user(current_user, db)
    return ClientService.create(db, agency.id, data)


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: str,
    data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a client (e.g. name) for the current user's agency."""
    agency = AgencyService.get_agency_for_user(current_user, db)
    return ClientService.update(db, agency.id, client_id, data)


@router.delete("/{client_id}", response_model=ClientResponse)
def archive_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive a client (soft delete). Fails if the client has campaigns."""
    agency = AgencyService.get_agency_for_user(current_user, db)
    return ClientService.archive(db, agency.id, client_id)

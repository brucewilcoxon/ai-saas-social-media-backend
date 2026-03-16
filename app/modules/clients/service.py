from sqlalchemy.orm import Session
from app.modules.clients.models import Client
from app.modules.clients.schemas import ClientCreate, ClientUpdate
from fastapi import HTTPException, status
from typing import List


class ClientService:
    @staticmethod
    def list_by_agency(db: Session, agency_id: str, active_only: bool = True) -> List[Client]:
        q = db.query(Client).filter(Client.agency_id == agency_id)
        if active_only:
            q = q.filter(Client.is_active == True)
        return q.all()

    @staticmethod
    def get_by_id(db: Session, agency_id: str, client_id: str) -> Client:
        client = db.query(Client).filter(
            Client.id == client_id,
            Client.agency_id == agency_id,
        ).first()
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
        return client

    @staticmethod
    def create(db: Session, agency_id: str, data: ClientCreate) -> Client:
        client = Client(agency_id=agency_id, name=data.name)
        db.add(client)
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def update(db: Session, agency_id: str, client_id: str, data: ClientUpdate) -> Client:
        client = ClientService.get_by_id(db, agency_id, client_id)
        client.name = data.name
        db.commit()
        db.refresh(client)
        return client

    @staticmethod
    def archive(db: Session, agency_id: str, client_id: str) -> Client:
        client = ClientService.get_by_id(db, agency_id, client_id)
        if client.campaigns:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot archive client with existing campaigns. Remove or reassign campaigns first.",
            )
        client.is_active = False
        db.commit()
        db.refresh(client)
        return client

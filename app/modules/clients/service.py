from sqlalchemy.orm import Session
from app.modules.clients.models import Client
from app.modules.clients.schemas import ClientCreate
from fastapi import HTTPException, status
from typing import List


class ClientService:
    @staticmethod
    def list_by_agency(db: Session, agency_id: str) -> List[Client]:
        return db.query(Client).filter(Client.agency_id == agency_id).all()

    @staticmethod
    def create(db: Session, agency_id: str, data: ClientCreate) -> Client:
        client = Client(agency_id=agency_id, name=data.name)
        db.add(client)
        db.commit()
        db.refresh(client)
        return client

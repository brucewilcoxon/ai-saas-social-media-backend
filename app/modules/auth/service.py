from sqlalchemy.orm import Session
from datetime import timedelta
from app.modules.auth.models import User, UserRole
from app.modules.auth.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.modules.auth.schemas import UserCreate, UserLogin, Token, RegisterOwnerRequest
from app.modules.tenants.service import TenantService
from app.modules.tenants.schemas import TenantCreate
from app.modules.tenants.models import Tenant
from app.modules.agencies.models import Agency
from app.modules.clients.models import Client
from app.config import settings
from app.utils.validators import validate_email, validate_password
from fastapi import HTTPException, status


class AuthService:
    @staticmethod
    def register_user(db: Session, user_data: UserCreate, tenant_id: str) -> User:
        """Register a new user"""
        # Validate email
        if not validate_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password
        is_valid, error_msg = validate_password(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Check if user exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        hashed_password = get_password_hash(user_data.password)
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role or UserRole.EDITOR,
            tenant_id=tenant_id
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def register_owner(db: Session, owner_data: RegisterOwnerRequest) -> tuple[User, Tenant]:
        """Register owner - creates tenant and owner user with ADMIN role"""
        # Validate email
        if not validate_email(owner_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password
        is_valid, error_msg = validate_password(owner_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Check if user exists
        existing_user = db.query(User).filter(User.email == owner_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create tenant
        tenant_data = TenantCreate(
            name=owner_data.tenant_name,
            slug=owner_data.tenant_slug
        )
        tenant = TenantService.create_tenant(db, tenant_data)

        # Create agency for this tenant (Milestone 2 multi-tenant)
        agency = Agency(
            tenant_id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=True,
        )
        db.add(agency)
        db.flush()

        # Create default client for agency
        client = Client(agency_id=agency.id, name=f"{tenant.name} - Default", is_active=True)
        db.add(client)
        db.flush()

        # Create owner user with ADMIN role
        hashed_password = get_password_hash(owner_data.password)
        user = User(
            email=owner_data.email,
            hashed_password=hashed_password,
            full_name=owner_data.full_name,
            role=UserRole.ADMIN,
            tenant_id=tenant.id,
            agency_id=agency.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return user, tenant
    
    @staticmethod
    def authenticate_user(db: Session, login_data: UserLogin) -> Token:
        """Authenticate user and return tokens"""
        user = db.query(User).filter(User.email == login_data.email).first()
        
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Create tokens with tenant_id in payload
        access_token = create_access_token(data={"sub": user.id, "tenant_id": user.tenant_id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        return Token(access_token=access_token, refresh_token=refresh_token)
    
    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> Token:
        """Refresh access token using refresh token"""
        from app.modules.auth.security import verify_token
        
        payload = verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens with tenant_id
        access_token = create_access_token(data={"sub": user.id, "tenant_id": user.tenant_id})
        new_refresh_token = create_refresh_token(data={"sub": user.id})
        
        return Token(access_token=access_token, refresh_token=new_refresh_token)

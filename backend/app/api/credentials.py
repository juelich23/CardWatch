"""
Auction house credential management REST API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.services.credential_manager import CredentialManager
from app.services.auction_auth.goldin_auth import GoldinAuthService
from app.services.auction_auth.fanatics_auth import FanaticsAuthService

router = APIRouter(prefix="/credentials", tags=["credentials"])


class StoreCredentialRequest(BaseModel):
    auction_house: str
    username: str
    password: str


class CredentialResponse(BaseModel):
    auction_house: str
    username_hint: str  # First 3 chars + ***
    is_valid: bool
    last_verified: str | None
    last_error: str | None


class LoginResponse(BaseModel):
    success: bool
    message: str


class CredentialStatusResponse(BaseModel):
    auction_house: str
    has_credentials: bool
    is_valid: bool | None
    has_active_session: bool


@router.post("", response_model=CredentialResponse)
async def store_credential(
    request: StoreCredentialRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Store credentials for an auction house (encrypted)"""
    manager = CredentialManager(db)

    try:
        credential = await manager.store_credentials(
            user_id=user.id,
            auction_house=request.auction_house.lower(),
            username=request.username,
            password=request.password
        )

        # Create username hint (first 3 chars + ***)
        username_hint = request.username[:3] + "***" if len(request.username) > 3 else "***"

        return CredentialResponse(
            auction_house=credential.auction_house,
            username_hint=username_hint,
            is_valid=credential.is_valid,
            last_verified=credential.last_verified.isoformat() if credential.last_verified else None,
            last_error=credential.last_error,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[CredentialResponse])
async def list_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all stored credentials for current user (passwords not returned)"""
    manager = CredentialManager(db)
    credentials = await manager.get_all_credentials(user.id)

    result = []
    for c in credentials:
        # Decrypt just to get username hint
        try:
            username, _ = manager.decrypt_credentials(c)
            username_hint = username[:3] + "***" if len(username) > 3 else "***"
        except Exception:
            username_hint = "***"

        result.append(CredentialResponse(
            auction_house=c.auction_house,
            username_hint=username_hint,
            is_valid=c.is_valid,
            last_verified=c.last_verified.isoformat() if c.last_verified else None,
            last_error=c.last_error,
        ))

    return result


@router.get("/status", response_model=list[CredentialStatusResponse])
async def get_credential_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get status of all auction house credentials"""
    manager = CredentialManager(db)

    statuses = []
    for house in CredentialManager.SUPPORTED_AUCTION_HOUSES:
        credential = await manager.get_credential(user.id, house)

        has_active_session = False
        if credential:
            if house == "goldin":
                goldin_auth = GoldinAuthService(db)
                has_active_session = await goldin_auth.is_session_valid(user.id)
            elif house == "fanatics":
                fanatics_auth = FanaticsAuthService(db)
                session = await fanatics_auth.get_active_session(user.id)
                has_active_session = session is not None

        statuses.append(CredentialStatusResponse(
            auction_house=house,
            has_credentials=credential is not None,
            is_valid=credential.is_valid if credential else None,
            has_active_session=has_active_session,
        ))

    return statuses


@router.delete("/{auction_house}")
async def delete_credential(
    auction_house: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete credentials for an auction house"""
    manager = CredentialManager(db)
    deleted = await manager.delete_credential(user.id, auction_house.lower())

    if not deleted:
        raise HTTPException(status_code=404, detail="Credential not found")

    return {"message": f"Credentials for {auction_house} deleted"}


@router.post("/{auction_house}/login", response_model=LoginResponse)
async def test_login(
    auction_house: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test login to an auction house (validates credentials)"""
    auction_house = auction_house.lower()

    if auction_house == "goldin":
        auth_service = GoldinAuthService(db)
        success, message = await auth_service.login(user.id)
        return LoginResponse(success=success, message=message)

    if auction_house == "fanatics":
        auth_service = FanaticsAuthService(db)
        success, message = await auth_service.login(user.id)
        return LoginResponse(success=success, message=message)

    raise HTTPException(
        status_code=400,
        detail=f"Login not yet implemented for {auction_house}"
    )


@router.post("/{auction_house}/logout")
async def logout(
    auction_house: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Invalidate active sessions for an auction house"""
    auction_house = auction_house.lower()
    manager = CredentialManager(db)

    credential = await manager.get_credential(user.id, auction_house)
    if not credential:
        raise HTTPException(status_code=404, detail="No credentials found")

    # Deactivate all sessions
    from sqlalchemy import select, update
    from app.models import UserSession

    await db.execute(
        update(UserSession)
        .where(UserSession.credential_id == credential.id)
        .values(is_active=False)
    )
    await db.commit()

    return {"message": f"Logged out of {auction_house}"}

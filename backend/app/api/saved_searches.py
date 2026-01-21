"""
Saved Searches REST API endpoints
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.deps import get_current_user
from app.models import User, SavedSearch

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


class SavedSearchFilters(BaseModel):
    """Filter configuration for a saved search"""
    search: Optional[str] = None
    auctionHouse: Optional[str] = None
    itemType: Optional[str] = None
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    sortBy: Optional[str] = None
    gradingCompany: Optional[str] = None
    category: Optional[str] = None


class SavedSearchCreate(BaseModel):
    """Request body for creating a saved search"""
    name: str
    filters: SavedSearchFilters
    email_alerts_enabled: bool = False


class SavedSearchUpdate(BaseModel):
    """Request body for updating a saved search"""
    name: Optional[str] = None
    filters: Optional[SavedSearchFilters] = None
    email_alerts_enabled: Optional[bool] = None


class SavedSearchResponse(BaseModel):
    """Response model for a saved search"""
    id: int
    name: str
    filters: dict
    email_alerts_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    request: SavedSearchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new saved search"""
    # Validate name
    if not request.name or len(request.name.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search name is required"
        )

    if len(request.name) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search name must be 100 characters or less"
        )

    # Check for duplicate name for this user
    existing_query = select(SavedSearch).where(
        SavedSearch.user_id == user.id,
        SavedSearch.name == request.name.strip()
    )
    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A saved search with this name already exists"
        )

    # Create saved search
    saved_search = SavedSearch(
        user_id=user.id,
        name=request.name.strip(),
        filters=request.filters.model_dump(exclude_none=True),
        email_alerts_enabled=request.email_alerts_enabled,
    )

    db.add(saved_search)
    await db.commit()
    await db.refresh(saved_search)

    return SavedSearchResponse(
        id=saved_search.id,
        name=saved_search.name,
        filters=saved_search.filters,
        email_alerts_enabled=saved_search.email_alerts_enabled,
        created_at=saved_search.created_at,
        updated_at=saved_search.updated_at,
    )


@router.get("", response_model=list[SavedSearchResponse])
async def list_saved_searches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all saved searches for the current user"""
    query = select(SavedSearch).where(
        SavedSearch.user_id == user.id
    ).order_by(SavedSearch.created_at.desc())

    result = await db.execute(query)
    searches = result.scalars().all()

    return [
        SavedSearchResponse(
            id=s.id,
            name=s.name,
            filters=s.filters,
            email_alerts_enabled=s.email_alerts_enabled,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in searches
    ]


@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single saved search by ID"""
    query = select(SavedSearch).where(
        SavedSearch.id == search_id,
        SavedSearch.user_id == user.id
    )

    result = await db.execute(query)
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    return SavedSearchResponse(
        id=saved_search.id,
        name=saved_search.name,
        filters=saved_search.filters,
        email_alerts_enabled=saved_search.email_alerts_enabled,
        created_at=saved_search.created_at,
        updated_at=saved_search.updated_at,
    )


@router.put("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: int,
    request: SavedSearchUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a saved search"""
    query = select(SavedSearch).where(
        SavedSearch.id == search_id,
        SavedSearch.user_id == user.id
    )

    result = await db.execute(query)
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    # Update fields if provided
    if request.name is not None:
        if len(request.name.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search name is required"
            )
        if len(request.name) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search name must be 100 characters or less"
            )

        # Check for duplicate name (excluding current search)
        existing_query = select(SavedSearch).where(
            SavedSearch.user_id == user.id,
            SavedSearch.name == request.name.strip(),
            SavedSearch.id != search_id
        )
        result = await db.execute(existing_query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A saved search with this name already exists"
            )

        saved_search.name = request.name.strip()

    if request.filters is not None:
        saved_search.filters = request.filters.model_dump(exclude_none=True)

    if request.email_alerts_enabled is not None:
        saved_search.email_alerts_enabled = request.email_alerts_enabled

    await db.commit()
    await db.refresh(saved_search)

    return SavedSearchResponse(
        id=saved_search.id,
        name=saved_search.name,
        filters=saved_search.filters,
        email_alerts_enabled=saved_search.email_alerts_enabled,
        created_at=saved_search.created_at,
        updated_at=saved_search.updated_at,
    )


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_search(
    search_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a saved search"""
    query = select(SavedSearch).where(
        SavedSearch.id == search_id,
        SavedSearch.user_id == user.id
    )

    result = await db.execute(query)
    saved_search = result.scalar_one_or_none()

    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )

    await db.delete(saved_search)
    await db.commit()

    return None

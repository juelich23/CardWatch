"""
User authentication service with JWT tokens and password hashing
"""
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models import User

settings = get_settings()

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    """User authentication service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None
    ) -> User:
        """Create a new user account"""
        user = User(
            email=email.lower(),
            hashed_password=self.hash_password(password),
            display_name=display_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await self.get_user_by_email(email)
        if not user or not self.verify_password(password, user.hashed_password):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        await self.db.commit()

        return user

    def create_access_token(
        self,
        user_id: int,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access"
        }
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    def create_refresh_token(self, user_id: int) -> str:
        """Create JWT refresh token"""
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh"
        }
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None

    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from access token"""
        payload = self.decode_token(token)
        if not payload or payload.get("type") != "access":
            return None

        user_id = int(payload.get("sub"))
        return await self.get_user_by_id(user_id)

"""
Credential manager for encrypted auction house credentials
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AuctionHouseCredential, UserSession
from app.services.encryption import get_encryption_service


class CredentialManager:
    """Manage encrypted auction house credentials"""

    SUPPORTED_AUCTION_HOUSES = ["goldin", "fanatics", "heritage", "pristine", "rea"]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = get_encryption_service()

    async def store_credentials(
        self,
        user_id: int,
        auction_house: str,
        username: str,
        password: str
    ) -> AuctionHouseCredential:
        """Store encrypted credentials for an auction house"""
        if auction_house not in self.SUPPORTED_AUCTION_HOUSES:
            raise ValueError(f"Unsupported auction house: {auction_house}")

        # Encrypt credentials
        encrypted_username, iv_username = self.encryption.encrypt(username)
        encrypted_password, iv_password = self.encryption.encrypt(password)

        # Combine IVs
        combined_iv = f"{iv_username}:{iv_password}"

        # Check for existing credential
        existing = await self.get_credential(user_id, auction_house)

        if existing:
            # Update existing
            existing.encrypted_username = encrypted_username
            existing.encrypted_password = encrypted_password
            existing.encryption_iv = combined_iv
            existing.is_valid = True  # Reset validity on update
            existing.last_error = None
            existing.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        # Create new
        credential = AuctionHouseCredential(
            user_id=user_id,
            auction_house=auction_house,
            encrypted_username=encrypted_username,
            encrypted_password=encrypted_password,
            encryption_iv=combined_iv,
        )
        self.db.add(credential)
        await self.db.commit()
        await self.db.refresh(credential)
        return credential

    async def get_credential(
        self,
        user_id: int,
        auction_house: str
    ) -> Optional[AuctionHouseCredential]:
        """Get credential for a specific auction house"""
        result = await self.db.execute(
            select(AuctionHouseCredential).where(
                AuctionHouseCredential.user_id == user_id,
                AuctionHouseCredential.auction_house == auction_house
            )
        )
        return result.scalar_one_or_none()

    async def get_all_credentials(self, user_id: int) -> List[AuctionHouseCredential]:
        """Get all credentials for a user"""
        result = await self.db.execute(
            select(AuctionHouseCredential).where(
                AuctionHouseCredential.user_id == user_id
            )
        )
        return list(result.scalars().all())

    def decrypt_credentials(self, credential: AuctionHouseCredential) -> tuple[str, str]:
        """Decrypt username and password from credential"""
        iv_username, iv_password = credential.encryption_iv.split(":")

        username = self.encryption.decrypt(credential.encrypted_username, iv_username)
        password = self.encryption.decrypt(credential.encrypted_password, iv_password)

        return username, password

    async def delete_credential(self, user_id: int, auction_house: str) -> bool:
        """Delete credential for an auction house"""
        credential = await self.get_credential(user_id, auction_house)
        if credential:
            await self.db.delete(credential)
            await self.db.commit()
            return True
        return False

    async def mark_credential_invalid(
        self,
        credential: AuctionHouseCredential,
        error_message: str
    ):
        """Mark credential as invalid after failed login"""
        credential.is_valid = False
        credential.last_error = error_message[:500]
        await self.db.commit()

    async def mark_credential_verified(self, credential: AuctionHouseCredential):
        """Mark credential as verified after successful login"""
        credential.is_valid = True
        credential.last_verified = datetime.utcnow()
        credential.last_error = None
        await self.db.commit()

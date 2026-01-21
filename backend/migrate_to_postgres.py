#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

Migrates all data from the SQLite database (auction_data.db) to a PostgreSQL database.
Handles the following tables: auctions, auction_items, users, user_watchlist_items, saved_searches

Usage:
    python migrate_to_postgres.py "postgresql://user:pass@host/db"
"""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import asyncpg
except ImportError:
    print("Error: asyncpg is not installed. Please install it with: pip install asyncpg")
    sys.exit(1)


# Path to SQLite database
SQLITE_DB_PATH = Path(__file__).parent / "auction_data.db"


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime string from SQLite to Python datetime object."""
    if value is None:
        return None
    try:
        # Try ISO format first
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            # Try common SQLite format
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                print(f"Warning: Could not parse datetime: {value}")
                return None


def parse_json(value: Optional[str]) -> Optional[Any]:
    """Parse JSON string from SQLite."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def get_sqlite_data(cursor: sqlite3.Cursor, table: str) -> tuple[list[str], list[tuple]]:
    """Fetch all data from a SQLite table."""
    cursor.execute(f"SELECT * FROM {table}")
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    return columns, rows


async def create_postgres_tables(conn: asyncpg.Connection) -> None:
    """Create all tables in PostgreSQL if they don't exist."""

    # Create tables in order (respecting foreign key constraints)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            display_name VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            last_login TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS auctions (
            id SERIAL PRIMARY KEY,
            auction_house VARCHAR(50) NOT NULL,
            external_id VARCHAR(255) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_auctions_auction_house ON auctions(auction_house);
        CREATE INDEX IF NOT EXISTS ix_auctions_external_id ON auctions(external_id);
        CREATE INDEX IF NOT EXISTS ix_auctions_category ON auctions(category);
        CREATE INDEX IF NOT EXISTS ix_auctions_end_time ON auctions(end_time);
        CREATE INDEX IF NOT EXISTS ix_auctions_status ON auctions(status);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_auction_house_external_id ON auctions(auction_house, external_id);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS auction_items (
            id SERIAL PRIMARY KEY,
            auction_id INTEGER REFERENCES auctions(id),
            auction_house VARCHAR(50) NOT NULL,
            external_id VARCHAR(255) NOT NULL,
            lot_number VARCHAR(100),
            cert_number VARCHAR(100),
            sub_category VARCHAR(100),
            grading_company VARCHAR(50),
            grade VARCHAR(20),
            title VARCHAR(500) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            sport VARCHAR(20),
            image_url VARCHAR(1000),
            image_urls JSONB,
            current_bid FLOAT,
            starting_bid FLOAT,
            reserve_price FLOAT,
            buy_now_price FLOAT,
            bid_count INTEGER DEFAULT 0,
            alt_price_estimate FLOAT,
            alt_price_data JSONB,
            market_value_low FLOAT,
            market_value_high FLOAT,
            market_value_avg FLOAT,
            market_value_confidence VARCHAR(20),
            market_value_notes VARCHAR(1000),
            market_value_updated_at TIMESTAMP,
            end_time TIMESTAMP,
            status VARCHAR(50) DEFAULT 'active',
            is_watched BOOLEAN DEFAULT FALSE,
            item_url VARCHAR(1000),
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_auction_items_auction_id ON auction_items(auction_id);
        CREATE INDEX IF NOT EXISTS ix_auction_items_auction_house ON auction_items(auction_house);
        CREATE INDEX IF NOT EXISTS ix_auction_items_external_id ON auction_items(external_id);
        CREATE INDEX IF NOT EXISTS ix_auction_items_sub_category ON auction_items(sub_category);
        CREATE INDEX IF NOT EXISTS ix_auction_items_grading_company ON auction_items(grading_company);
        CREATE INDEX IF NOT EXISTS ix_auction_items_category ON auction_items(category);
        CREATE INDEX IF NOT EXISTS ix_auction_items_sport ON auction_items(sport);
        CREATE INDEX IF NOT EXISTS ix_auction_items_current_bid ON auction_items(current_bid);
        CREATE INDEX IF NOT EXISTS ix_auction_items_end_time ON auction_items(end_time);
        CREATE INDEX IF NOT EXISTS ix_auction_items_status ON auction_items(status);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_item_auction_house_external_id ON auction_items(auction_house, external_id);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_watchlist_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            item_id INTEGER REFERENCES auction_items(id) NOT NULL,
            added_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_user_watchlist_items_user_id ON user_watchlist_items(user_id);
        CREATE INDEX IF NOT EXISTS ix_user_watchlist_items_item_id ON user_watchlist_items(item_id);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_user_watchlist_unique ON user_watchlist_items(user_id, item_id);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_searches (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            name VARCHAR(100) NOT NULL,
            filters JSONB NOT NULL,
            email_alerts_enabled BOOLEAN DEFAULT FALSE,
            last_alert_sent TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_saved_searches_user_id ON saved_searches(user_id);
    """)

    print("PostgreSQL tables created successfully.")


async def migrate_users(sqlite_cursor: sqlite3.Cursor, pg_conn: asyncpg.Connection) -> dict[int, int]:
    """Migrate users table. Returns mapping of old IDs to new IDs."""
    print("\nMigrating users...")

    columns, rows = get_sqlite_data(sqlite_cursor, "users")

    if not rows:
        print("  No users to migrate.")
        return {}

    id_mapping = {}
    migrated = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        old_id = row_dict["id"]

        try:
            new_id = await pg_conn.fetchval("""
                INSERT INTO users (email, hashed_password, display_name, is_active, is_verified,
                                   created_at, updated_at, last_login)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (email) DO UPDATE SET
                    hashed_password = EXCLUDED.hashed_password,
                    display_name = EXCLUDED.display_name,
                    is_active = EXCLUDED.is_active,
                    is_verified = EXCLUDED.is_verified,
                    updated_at = EXCLUDED.updated_at,
                    last_login = EXCLUDED.last_login
                RETURNING id
            """,
                row_dict["email"],
                row_dict["hashed_password"],
                row_dict.get("display_name"),
                bool(row_dict.get("is_active", True)),
                bool(row_dict.get("is_verified", False)),
                parse_datetime(row_dict.get("created_at")),
                parse_datetime(row_dict.get("updated_at")),
                parse_datetime(row_dict.get("last_login"))
            )

            id_mapping[old_id] = new_id
            migrated += 1

        except Exception as e:
            print(f"  Error migrating user {row_dict['email']}: {e}")

    print(f"  Migrated {migrated}/{len(rows)} users.")
    return id_mapping


async def migrate_auctions(sqlite_cursor: sqlite3.Cursor, pg_conn: asyncpg.Connection) -> dict[int, int]:
    """Migrate auctions table. Returns mapping of old IDs to new IDs."""
    print("\nMigrating auctions...")

    columns, rows = get_sqlite_data(sqlite_cursor, "auctions")

    if not rows:
        print("  No auctions to migrate.")
        return {}

    id_mapping = {}
    migrated = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        old_id = row_dict["id"]

        try:
            new_id = await pg_conn.fetchval("""
                INSERT INTO auctions (auction_house, external_id, title, description, category,
                                      start_time, end_time, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (auction_house, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
            """,
                row_dict["auction_house"],
                row_dict["external_id"],
                row_dict["title"],
                row_dict.get("description"),
                row_dict.get("category"),
                parse_datetime(row_dict.get("start_time")),
                parse_datetime(row_dict.get("end_time")),
                row_dict.get("status", "active"),
                parse_datetime(row_dict.get("created_at")),
                parse_datetime(row_dict.get("updated_at"))
            )

            id_mapping[old_id] = new_id
            migrated += 1

            if migrated % 100 == 0:
                print(f"  Migrated {migrated} auctions...")

        except Exception as e:
            print(f"  Error migrating auction {row_dict['external_id']}: {e}")

    print(f"  Migrated {migrated}/{len(rows)} auctions.")
    return id_mapping


async def migrate_auction_items(
    sqlite_cursor: sqlite3.Cursor,
    pg_conn: asyncpg.Connection,
    auction_id_mapping: dict[int, int]
) -> dict[int, int]:
    """Migrate auction_items table. Returns mapping of old IDs to new IDs."""
    print("\nMigrating auction items...")

    columns, rows = get_sqlite_data(sqlite_cursor, "auction_items")

    if not rows:
        print("  No auction items to migrate.")
        return {}

    id_mapping = {}
    migrated = 0
    skipped = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        old_id = row_dict["id"]
        old_auction_id = row_dict.get("auction_id")

        # Map auction_id to new ID if it exists
        new_auction_id = auction_id_mapping.get(old_auction_id) if old_auction_id else None

        if old_auction_id and not new_auction_id:
            print(f"  Warning: auction_id {old_auction_id} not found for item {old_id}")
            skipped += 1
            continue

        try:
            new_id = await pg_conn.fetchval("""
                INSERT INTO auction_items (
                    auction_id, auction_house, external_id, lot_number, cert_number,
                    sub_category, grading_company, grade, title, description,
                    category, sport, image_url, image_urls, current_bid,
                    starting_bid, reserve_price, buy_now_price, bid_count,
                    alt_price_estimate, alt_price_data, market_value_low, market_value_high,
                    market_value_avg, market_value_confidence, market_value_notes,
                    market_value_updated_at, end_time, status, is_watched,
                    item_url, raw_data, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                        $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28,
                        $29, $30, $31, $32, $33, $34)
                ON CONFLICT (auction_house, external_id) DO UPDATE SET
                    auction_id = EXCLUDED.auction_id,
                    lot_number = EXCLUDED.lot_number,
                    cert_number = EXCLUDED.cert_number,
                    sub_category = EXCLUDED.sub_category,
                    grading_company = EXCLUDED.grading_company,
                    grade = EXCLUDED.grade,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    sport = EXCLUDED.sport,
                    image_url = EXCLUDED.image_url,
                    image_urls = EXCLUDED.image_urls,
                    current_bid = EXCLUDED.current_bid,
                    starting_bid = EXCLUDED.starting_bid,
                    reserve_price = EXCLUDED.reserve_price,
                    buy_now_price = EXCLUDED.buy_now_price,
                    bid_count = EXCLUDED.bid_count,
                    alt_price_estimate = EXCLUDED.alt_price_estimate,
                    alt_price_data = EXCLUDED.alt_price_data,
                    market_value_low = EXCLUDED.market_value_low,
                    market_value_high = EXCLUDED.market_value_high,
                    market_value_avg = EXCLUDED.market_value_avg,
                    market_value_confidence = EXCLUDED.market_value_confidence,
                    market_value_notes = EXCLUDED.market_value_notes,
                    market_value_updated_at = EXCLUDED.market_value_updated_at,
                    end_time = EXCLUDED.end_time,
                    status = EXCLUDED.status,
                    is_watched = EXCLUDED.is_watched,
                    item_url = EXCLUDED.item_url,
                    raw_data = EXCLUDED.raw_data,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
            """,
                new_auction_id,
                row_dict["auction_house"],
                row_dict["external_id"],
                row_dict.get("lot_number"),
                row_dict.get("cert_number"),
                row_dict.get("sub_category"),
                row_dict.get("grading_company"),
                row_dict.get("grade"),
                row_dict["title"],
                row_dict.get("description"),
                row_dict.get("category"),
                row_dict.get("sport"),
                row_dict.get("image_url"),
                json.dumps(parse_json(row_dict.get("image_urls"))) if row_dict.get("image_urls") else None,
                row_dict.get("current_bid"),
                row_dict.get("starting_bid"),
                row_dict.get("reserve_price"),
                row_dict.get("buy_now_price"),
                row_dict.get("bid_count", 0),
                row_dict.get("alt_price_estimate"),
                json.dumps(parse_json(row_dict.get("alt_price_data"))) if row_dict.get("alt_price_data") else None,
                row_dict.get("market_value_low"),
                row_dict.get("market_value_high"),
                row_dict.get("market_value_avg"),
                row_dict.get("market_value_confidence"),
                row_dict.get("market_value_notes"),
                parse_datetime(row_dict.get("market_value_updated_at")),
                parse_datetime(row_dict.get("end_time")),
                row_dict.get("status", "active"),
                bool(row_dict.get("is_watched", False)),
                row_dict.get("item_url"),
                json.dumps(parse_json(row_dict.get("raw_data"))) if row_dict.get("raw_data") else None,
                parse_datetime(row_dict.get("created_at")),
                parse_datetime(row_dict.get("updated_at"))
            )

            id_mapping[old_id] = new_id
            migrated += 1

            if migrated % 500 == 0:
                print(f"  Migrated {migrated} auction items...")

        except Exception as e:
            print(f"  Error migrating auction item {row_dict['external_id']}: {e}")
            skipped += 1

    print(f"  Migrated {migrated}/{len(rows)} auction items ({skipped} skipped).")
    return id_mapping


async def migrate_user_watchlist_items(
    sqlite_cursor: sqlite3.Cursor,
    pg_conn: asyncpg.Connection,
    user_id_mapping: dict[int, int],
    item_id_mapping: dict[int, int]
) -> None:
    """Migrate user_watchlist_items table."""
    print("\nMigrating user watchlist items...")

    columns, rows = get_sqlite_data(sqlite_cursor, "user_watchlist_items")

    if not rows:
        print("  No watchlist items to migrate.")
        return

    migrated = 0
    skipped = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        old_user_id = row_dict["user_id"]
        old_item_id = row_dict["item_id"]

        new_user_id = user_id_mapping.get(old_user_id)
        new_item_id = item_id_mapping.get(old_item_id)

        if not new_user_id:
            print(f"  Warning: user_id {old_user_id} not found")
            skipped += 1
            continue

        if not new_item_id:
            print(f"  Warning: item_id {old_item_id} not found")
            skipped += 1
            continue

        try:
            await pg_conn.execute("""
                INSERT INTO user_watchlist_items (user_id, item_id, added_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, item_id) DO NOTHING
            """,
                new_user_id,
                new_item_id,
                parse_datetime(row_dict.get("added_at"))
            )
            migrated += 1

        except Exception as e:
            print(f"  Error migrating watchlist item: {e}")
            skipped += 1

    print(f"  Migrated {migrated}/{len(rows)} watchlist items ({skipped} skipped).")


async def migrate_saved_searches(
    sqlite_cursor: sqlite3.Cursor,
    pg_conn: asyncpg.Connection,
    user_id_mapping: dict[int, int]
) -> None:
    """Migrate saved_searches table."""
    print("\nMigrating saved searches...")

    columns, rows = get_sqlite_data(sqlite_cursor, "saved_searches")

    if not rows:
        print("  No saved searches to migrate.")
        return

    migrated = 0
    skipped = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        old_user_id = row_dict["user_id"]

        new_user_id = user_id_mapping.get(old_user_id)

        if not new_user_id:
            print(f"  Warning: user_id {old_user_id} not found")
            skipped += 1
            continue

        try:
            filters = parse_json(row_dict.get("filters"))
            if filters is None:
                filters = {}

            await pg_conn.execute("""
                INSERT INTO saved_searches (user_id, name, filters, email_alerts_enabled,
                                           last_alert_sent, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                new_user_id,
                row_dict["name"],
                json.dumps(filters),
                bool(row_dict.get("email_alerts_enabled", False)),
                parse_datetime(row_dict.get("last_alert_sent")),
                parse_datetime(row_dict.get("created_at")),
                parse_datetime(row_dict.get("updated_at"))
            )
            migrated += 1

        except Exception as e:
            print(f"  Error migrating saved search '{row_dict['name']}': {e}")
            skipped += 1

    print(f"  Migrated {migrated}/{len(rows)} saved searches ({skipped} skipped).")


async def reset_sequences(pg_conn: asyncpg.Connection) -> None:
    """Reset PostgreSQL sequences to match the max IDs in each table."""
    print("\nResetting PostgreSQL sequences...")

    tables = ["users", "auctions", "auction_items", "user_watchlist_items", "saved_searches"]

    for table in tables:
        try:
            max_id = await pg_conn.fetchval(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
            if max_id > 0:
                await pg_conn.execute(f"SELECT setval('{table}_id_seq', $1)", max_id)
                print(f"  Reset {table}_id_seq to {max_id}")
        except Exception as e:
            print(f"  Warning: Could not reset sequence for {table}: {e}")


async def main(postgres_url: str) -> None:
    """Main migration function."""
    print("=" * 60)
    print("SQLite to PostgreSQL Migration")
    print("=" * 60)

    # Check SQLite database exists
    if not SQLITE_DB_PATH.exists():
        print(f"Error: SQLite database not found at {SQLITE_DB_PATH}")
        sys.exit(1)

    print(f"\nSource: {SQLITE_DB_PATH}")
    print(f"Target: {postgres_url.split('@')[1] if '@' in postgres_url else postgres_url}")

    # Connect to SQLite
    print("\nConnecting to SQLite database...")
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL
    print("Connecting to PostgreSQL database...")
    try:
        pg_conn = await asyncpg.connect(postgres_url)
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sqlite_conn.close()
        sys.exit(1)

    try:
        # Create tables
        await create_postgres_tables(pg_conn)

        # Migrate data in correct order (respecting foreign keys)
        user_id_mapping = await migrate_users(sqlite_cursor, pg_conn)
        auction_id_mapping = await migrate_auctions(sqlite_cursor, pg_conn)
        item_id_mapping = await migrate_auction_items(sqlite_cursor, pg_conn, auction_id_mapping)
        await migrate_user_watchlist_items(sqlite_cursor, pg_conn, user_id_mapping, item_id_mapping)
        await migrate_saved_searches(sqlite_cursor, pg_conn, user_id_mapping)

        # Reset sequences
        await reset_sequences(pg_conn)

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nMigration failed with error: {e}")
        raise
    finally:
        sqlite_conn.close()
        await pg_conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python migrate_to_postgres.py \"postgresql://user:pass@host/db\"")
        print("\nExample:")
        print("  python migrate_to_postgres.py \"postgresql://postgres:password@localhost:5432/bulkbidding\"")
        sys.exit(1)

    postgres_url = sys.argv[1]

    if not postgres_url.startswith("postgresql://") and not postgres_url.startswith("postgres://"):
        print("Error: Invalid PostgreSQL connection string.")
        print("Connection string must start with 'postgresql://' or 'postgres://'")
        sys.exit(1)

    asyncio.run(main(postgres_url))

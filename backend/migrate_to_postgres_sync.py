#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script (Synchronous version using psycopg2)

Migrates all data from the SQLite database (auction_data.db) to a PostgreSQL database.
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Error: psycopg2 is not installed. Please install it with: pip install psycopg2-binary")
    sys.exit(1)

# Path to SQLite database
SQLITE_DB_PATH = Path(__file__).parent / "auction_data.db"


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse datetime string from SQLite to Python datetime object."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
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


def create_postgres_tables(cursor) -> None:
    """Create all tables in PostgreSQL if they don't exist."""

    cursor.execute("""
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

    cursor.execute("""
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
        CREATE INDEX IF NOT EXISTS ix_auctions_status ON auctions(status);
    """)

    # Check if unique index exists before creating
    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_auction_house_external_id') THEN
                CREATE UNIQUE INDEX ix_auction_house_external_id ON auctions(auction_house, external_id);
            END IF;
        END $$;
    """)

    cursor.execute("""
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
        CREATE INDEX IF NOT EXISTS ix_auction_items_auction_house ON auction_items(auction_house);
        CREATE INDEX IF NOT EXISTS ix_auction_items_external_id ON auction_items(external_id);
        CREATE INDEX IF NOT EXISTS ix_auction_items_status ON auction_items(status);
        CREATE INDEX IF NOT EXISTS ix_auction_items_current_bid ON auction_items(current_bid);
    """)

    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_item_auction_house_external_id') THEN
                CREATE UNIQUE INDEX ix_item_auction_house_external_id ON auction_items(auction_house, external_id);
            END IF;
        END $$;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id SERIAL PRIMARY KEY,
            item_id INTEGER REFERENCES auction_items(id),
            snapshot_date TIMESTAMP DEFAULT NOW(),
            current_bid FLOAT,
            bid_count INTEGER DEFAULT 0,
            status VARCHAR(50)
        );
        CREATE INDEX IF NOT EXISTS ix_price_snapshots_item_id ON price_snapshots(item_id);
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_watchlist_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            item_id INTEGER REFERENCES auction_items(id) NOT NULL,
            added_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_user_watchlist_items_user_id ON user_watchlist_items(user_id);
    """)

    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_user_watchlist_unique') THEN
                CREATE UNIQUE INDEX ix_user_watchlist_unique ON user_watchlist_items(user_id, item_id);
            END IF;
        END $$;
    """)

    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            token VARCHAR(500) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_user_sessions_token ON user_sessions(token);
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auction_house_credentials (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) NOT NULL,
            auction_house VARCHAR(50) NOT NULL,
            encrypted_credentials TEXT NOT NULL,
            session_data TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            last_verified TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    print("PostgreSQL tables created successfully.")


def migrate_auctions(sqlite_cursor, pg_cursor) -> dict[int, int]:
    """Migrate auctions table."""
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
            pg_cursor.execute("""
                INSERT INTO auctions (auction_house, external_id, title, description, category,
                                      start_time, end_time, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (auction_house, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
            """, (
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
            ))

            new_id = pg_cursor.fetchone()[0]
            id_mapping[old_id] = new_id
            migrated += 1

        except Exception as e:
            print(f"  Error migrating auction {row_dict['external_id']}: {e}")

    print(f"  Migrated {migrated}/{len(rows)} auctions.")
    return id_mapping


def migrate_auction_items(sqlite_cursor, pg_cursor, auction_id_mapping: dict[int, int]) -> dict[int, int]:
    """Migrate auction_items table."""
    print("\nMigrating auction items...")

    columns, rows = get_sqlite_data(sqlite_cursor, "auction_items")

    if not rows:
        print("  No auction items to migrate.")
        return {}

    id_mapping = {}
    migrated = 0

    for row in rows:
        row_dict = dict(zip(columns, row))
        old_id = row_dict["id"]
        old_auction_id = row_dict.get("auction_id")
        new_auction_id = auction_id_mapping.get(old_auction_id) if old_auction_id else None

        try:
            image_urls = parse_json(row_dict.get("image_urls"))
            alt_price_data = parse_json(row_dict.get("alt_price_data"))
            raw_data = parse_json(row_dict.get("raw_data"))

            pg_cursor.execute("""
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s)
                ON CONFLICT (auction_house, external_id) DO UPDATE SET
                    current_bid = EXCLUDED.current_bid,
                    bid_count = EXCLUDED.bid_count,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
            """, (
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
                json.dumps(image_urls) if image_urls else None,
                row_dict.get("current_bid"),
                row_dict.get("starting_bid"),
                row_dict.get("reserve_price"),
                row_dict.get("buy_now_price"),
                row_dict.get("bid_count", 0),
                row_dict.get("alt_price_estimate"),
                json.dumps(alt_price_data) if alt_price_data else None,
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
                json.dumps(raw_data) if raw_data else None,
                parse_datetime(row_dict.get("created_at")),
                parse_datetime(row_dict.get("updated_at"))
            ))

            new_id = pg_cursor.fetchone()[0]
            id_mapping[old_id] = new_id
            migrated += 1

            if migrated % 500 == 0:
                print(f"  Migrated {migrated} auction items...")

        except Exception as e:
            print(f"  Error migrating item {row_dict.get('external_id')}: {e}")

    print(f"  Migrated {migrated}/{len(rows)} auction items.")
    return id_mapping


def migrate_users(sqlite_cursor, pg_cursor) -> dict[int, int]:
    """Migrate users table."""
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
            pg_cursor.execute("""
                INSERT INTO users (email, hashed_password, display_name, is_active, is_verified,
                                   created_at, updated_at, last_login)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET updated_at = EXCLUDED.updated_at
                RETURNING id
            """, (
                row_dict["email"],
                row_dict["hashed_password"],
                row_dict.get("display_name"),
                bool(row_dict.get("is_active", True)),
                bool(row_dict.get("is_verified", False)),
                parse_datetime(row_dict.get("created_at")),
                parse_datetime(row_dict.get("updated_at")),
                parse_datetime(row_dict.get("last_login"))
            ))

            new_id = pg_cursor.fetchone()[0]
            id_mapping[old_id] = new_id
            migrated += 1

        except Exception as e:
            print(f"  Error migrating user {row_dict['email']}: {e}")

    print(f"  Migrated {migrated}/{len(rows)} users.")
    return id_mapping


def main(postgres_url: str) -> None:
    """Main migration function."""
    print("=" * 60)
    print("SQLite to PostgreSQL Migration (psycopg2)")
    print("=" * 60)

    if not SQLITE_DB_PATH.exists():
        print(f"Error: SQLite database not found at {SQLITE_DB_PATH}")
        sys.exit(1)

    print(f"\nSource: {SQLITE_DB_PATH}")

    # Connect to SQLite
    print("\nConnecting to SQLite database...")
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL with SSL
    print("Connecting to PostgreSQL database...")
    try:
        pg_conn = psycopg2.connect(postgres_url, sslmode='require')
        pg_conn.autocommit = False
        pg_cursor = pg_conn.cursor()
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sqlite_conn.close()
        sys.exit(1)

    try:
        # Create tables
        create_postgres_tables(pg_cursor)
        pg_conn.commit()

        # Migrate data
        user_id_mapping = migrate_users(sqlite_cursor, pg_cursor)
        pg_conn.commit()

        auction_id_mapping = migrate_auctions(sqlite_cursor, pg_cursor)
        pg_conn.commit()

        item_id_mapping = migrate_auction_items(sqlite_cursor, pg_cursor, auction_id_mapping)
        pg_conn.commit()

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        pg_conn.rollback()
        print(f"\nMigration failed: {e}")
        raise
    finally:
        sqlite_conn.close()
        pg_cursor.close()
        pg_conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python migrate_to_postgres_sync.py \"postgresql://...\"")
        sys.exit(1)

    postgres_url = sys.argv[1]
    main(postgres_url)

import asyncpg
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DATABASE_URL

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                age INTEGER,
                role TEXT,
                profit INTEGER DEFAULT 0,
                recruited_streamers INTEGER DEFAULT 0,
                streams_count INTEGER DEFAULT 0,
                join_date TIMESTAMP,
                approved BOOLEAN DEFAULT FALSE,
                last_active TIMESTAMP,
                avatar_file_id TEXT,
                notification_settings BOOLEAN DEFAULT TRUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_app (
                user_id BIGINT PRIMARY KEY,
                age TEXT,
                hours_per_day TEXT,
                experience TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS profit_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                timestamp TIMESTAMP,
                source TEXT,
                admin_id BIGINT
            )
        """)
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ('welcome_gif_file_id', '')
            ON CONFLICT (key) DO NOTHING
        """)
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ('chat_link', '')
            ON CONFLICT (key) DO NOTHING
        """)
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ('application_channel_id', '')
            ON CONFLICT (key) DO NOTHING
        """)
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ('log_channel_id', '')
            ON CONFLICT (key) DO NOTHING
        """)

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None

async def create_user(user_id: int, username: str, age: int, role: str = "новичок") -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, display_name, age, role, profit, recruited_streamers, streams_count, join_date, approved, last_active, avatar_file_id, notification_settings)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                display_name = EXCLUDED.display_name,
                age = EXCLUDED.age,
                role = EXCLUDED.role,
                join_date = EXCLUDED.join_date,
                approved = EXCLUDED.approved,
                last_active = EXCLUDED.last_active
        """, user_id, username, username, age, role, 0, 0, 0, datetime.now(), True, datetime.now(), None, True)

async def update_user(user_id: int, **kwargs) -> None:
    if not kwargs:
        return
    async with db_pool.acquire() as conn:
        set_clause = ", ".join([f"{key} = ${i+2}" for i, key in enumerate(kwargs.keys())])
        values = [user_id] + list(kwargs.values())
        query = f"UPDATE users SET {set_clause} WHERE user_id = $1"
        await conn.execute(query, *values)

async def update_last_active(user_id: int) -> None:
    await update_user(user_id, last_active=datetime.now())

async def add_profit(user_id: int, amount: int, source: str, admin_id: int = None) -> None:
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE users SET profit = profit + $1 WHERE user_id = $2", amount, user_id)
            await conn.execute("""
                INSERT INTO profit_logs (user_id, amount, timestamp, source, admin_id)
                VALUES ($1, $2, $3, $4, $5)
            """, user_id, amount, datetime.now(), source, admin_id)

async def get_all_users(only_approved: bool = True) -> List[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        if only_approved:
            rows = await conn.fetch("SELECT * FROM users WHERE approved = TRUE")
        else:
            rows = await conn.fetch("SELECT * FROM users")
        return [dict(row) for row in rows]

async def get_active_users_last_days(days: int = 7) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COUNT(*) FROM users 
            WHERE approved = TRUE AND last_active >= NOW() - ($1 || ' days')::interval
        """, days)
        return row[0] if row else 0

async def save_pending_app(user_id: int, age: str, hours: str, experience: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO pending_app (user_id, age, hours_per_day, experience)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                age = EXCLUDED.age,
                hours_per_day = EXCLUDED.hours_per_day,
                experience = EXCLUDED.experience
        """, user_id, age, hours, experience)

async def get_pending_app(user_id: int) -> Optional[Dict[str, Any]]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pending_app WHERE user_id = $1", user_id)
        return dict(row) if row else None

async def delete_pending_app(user_id: int) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM pending_app WHERE user_id = $1", user_id)

async def get_setting(key: str) -> Optional[str]:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row[0] if row else None

async def set_setting(key: str, value: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, value)

async def get_team_stats() -> Dict[str, Any]:
    users = await get_all_users(only_approved=True)
    total = len(users)
    streamers = sum(1 for u in users if u['role'] == 'стримерша')
    traffers = sum(1 for u in users if u['role'] == 'трафер')
    moders = sum(1 for u in users if u['role'] == 'модератор')
    total_profit = sum(u['profit'] for u in users)
    active_week = await get_active_users_last_days(7)
    return {
        "total": total,
        "streamers": streamers,
        "traffers": traffers,
        "moders": moders,
        "total_profit": total_profit,
        "active_week": active_week
    }
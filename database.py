# ════════════════════════════════════════════
# 🃏 Card Collection Bot — Database Layer
# ════════════════════════════════════════════
import aiosqlite
import asyncio
import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from config import DB_PATH, STARTING_COINS

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            first_name  TEXT,
            coins       INTEGER DEFAULT 1000,
            level       INTEGER DEFAULT 1,
            xp          INTEGER DEFAULT 0,
            streak      INTEGER DEFAULT 0,
            last_daily  TEXT,
            married_to  INTEGER DEFAULT NULL,
            active_title TEXT DEFAULT 't1',
            total_caught INTEGER DEFAULT 0,
            total_spent  INTEGER DEFAULT 0,
            slots_wins   INTEGER DEFAULT 0,
            jackpots     INTEGER DEFAULT 0,
            best_combo   INTEGER DEFAULT 0,
            days_played  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cards (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            movie       TEXT NOT NULL,
            rarity      TEXT DEFAULT 'Common',
            file_id     TEXT,
            file_type   TEXT DEFAULT 'photo',
            drop_rate   REAL DEFAULT 1.0,
            uploaded_by INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_cards (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            card_id     INTEGER,
            is_favorite INTEGER DEFAULT 0,
            caught_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(card_id) REFERENCES cards(id)
        );

        CREATE TABLE IF NOT EXISTS shop_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key    TEXT UNIQUE,
            name        TEXT,
            description TEXT,
            price       INTEGER,
            effect      TEXT,
            duration    INTEGER DEFAULT 0,
            available_until TEXT DEFAULT NULL,
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS user_inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            item_key    TEXT,
            quantity    INTEGER DEFAULT 1,
            expires_at  TEXT DEFAULT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS friends (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            friend_id   INTEGER,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, friend_id)
        );

        CREATE TABLE IF NOT EXISTS sudo_admins (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            added_by    INTEGER,
            added_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user   INTEGER,
            to_user     INTEGER,
            amount      INTEGER,
            tx_type     TEXT,
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS missions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_key TEXT UNIQUE,
            name        TEXT,
            description TEXT,
            mission_type TEXT,
            requirement INTEGER,
            reward      INTEGER,
            period      TEXT
        );

        CREATE TABLE IF NOT EXISTS user_missions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            mission_key TEXT,
            progress    INTEGER DEFAULT 0,
            completed   INTEGER DEFAULT 0,
            reset_at    TEXT,
            UNIQUE(user_id, mission_key)
        );

        CREATE TABLE IF NOT EXISTS achievements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ach_key     TEXT UNIQUE,
            name        TEXT,
            description TEXT,
            badge       TEXT,
            req_type    TEXT,
            req_value   INTEGER
        );

        CREATE TABLE IF NOT EXISTS user_achievements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            ach_key     TEXT,
            earned_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, ach_key)
        );

        CREATE TABLE IF NOT EXISTS titles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title_key   TEXT UNIQUE,
            name        TEXT,
            description TEXT,
            condition   TEXT,
            emoji       TEXT
        );

        CREATE TABLE IF NOT EXISTS user_titles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            title_key   TEXT,
            earned_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, title_key)
        );

        CREATE TABLE IF NOT EXISTS drop_settings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            base_rate   REAL DEFAULT 1.0,
            current_rate REAL DEFAULT 1.0,
            set_by      INTEGER,
            note        TEXT,
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS backups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT,
            size_bytes  INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS weekly_board (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            weekly_coins INTEGER DEFAULT 0,
            week_start  TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id    INTEGER,
            action      TEXT,
            target      TEXT,
            details     TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        INSERT OR IGNORE INTO drop_settings (base_rate, current_rate, set_by, note)
        VALUES (1.0, 1.0, 0, 'default');
        """)
        await db.commit()
    log.info("✅ Database initialized")

# ─────────────────────────────────────────────
# USER OPERATIONS
# ─────────────────────────────────────────────
async def get_or_create_user(user_id: int, username: str = "", first_name: str = "") -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, coins) VALUES (?,?,?,?)",
                (user_id, username, first_name, STARTING_COINS)
            )
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
        return dict(row)

async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {cols} WHERE user_id=?", vals)
        await db.commit()

async def add_coins(user_id: int, amount: int, tx_type: str = "reward", from_user: int = 0, note: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
        await db.execute(
            "INSERT INTO transactions (from_user, to_user, amount, tx_type, note) VALUES (?,?,?,?,?)",
            (from_user, user_id, amount, tx_type, note)
        )
        if amount > 0:
            await db.execute(
                "UPDATE weekly_board SET weekly_coins = weekly_coins + ? WHERE user_id=?",
                (amount, user_id)
            )
        await db.commit()

async def add_xp(user_id: int, amount: int) -> Dict:
    """Add XP and handle level ups. Returns {leveled_up, new_level}"""
    from config import LEVEL_XP_REQUIREMENTS
    user = await get_user(user_id)
    if not user:
        return {"leveled_up": False, "new_level": 1}

    new_xp   = user["xp"] + amount
    new_level = user["level"]
    leveled_up = False

    while new_level < len(LEVEL_XP_REQUIREMENTS) - 1:
        if new_xp >= LEVEL_XP_REQUIREMENTS[new_level]:
            new_level += 1
            leveled_up = True
        else:
            break

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET xp=?, level=? WHERE user_id=?",
            (new_xp, new_level, user_id)
        )
        await db.commit()
    return {"leveled_up": leveled_up, "new_level": new_level, "xp": new_xp}

async def ensure_weekly_entry(user_id: int, username: str):
    from datetime import date, timedelta
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM weekly_board WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO weekly_board (user_id, username, weekly_coins, week_start) VALUES (?,?,0,?)",
                (user_id, username, str(monday))
            )
        else:
            await db.execute(
                "UPDATE weekly_board SET username=? WHERE user_id=?",
                (username, user_id)
            )
        await db.commit()

# ─────────────────────────────────────────────
# CARD OPERATIONS
# ─────────────────────────────────────────────
async def add_card(name: str, movie: str, rarity: str, file_id: str,
                   file_type: str, uploaded_by: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO cards (name, movie, rarity, file_id, file_type, uploaded_by) VALUES (?,?,?,?,?,?)",
            (name, movie, rarity, file_id, file_type, uploaded_by)
        )
        await db.commit()
        return cur.lastrowid

async def get_card(card_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM cards WHERE id=?", (card_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

async def get_card_by_name(name: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM cards WHERE LOWER(name) LIKE ?", (f"%{name.lower()}%",)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

async def delete_card(card_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cards WHERE id=?", (card_id,))
        await db.execute("DELETE FROM user_cards WHERE card_id=?", (card_id,))
        await db.commit()

async def edit_card(card_id: int, name: str, movie: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE cards SET name=?, movie=? WHERE id=?",
            (name, movie, card_id)
        )
        await db.commit()

async def get_random_card(rarity: Optional[str] = None) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if rarity:
            async with db.execute(
                "SELECT * FROM cards WHERE rarity=? ORDER BY RANDOM() LIMIT 1", (rarity,)
            ) as cur:
                row = await cur.fetchone()
        else:
            async with db.execute(
                "SELECT * FROM cards ORDER BY RANDOM() LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None

async def get_all_cards(page: int = 1, per_page: int = 10) -> List[Dict]:
    offset = (page - 1) * per_page
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM cards ORDER BY rarity, name LIMIT ? OFFSET ?",
            (per_page, offset)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def count_cards() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM cards") as cur:
            row = await cur.fetchone()
        return row[0]

async def add_card_to_user(user_id: int, card_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_cards (user_id, card_id) VALUES (?,?)",
            (user_id, card_id)
        )
        await db.execute(
            "UPDATE users SET total_caught = total_caught + 1 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()

async def get_user_cards(user_id: int, sort: str = "rarity", page: int = 1) -> List[Dict]:
    per_page = 12
    offset   = (page - 1) * per_page
    order    = "c.rarity DESC, c.name" if sort == "rarity" else "uc.caught_at DESC"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"""
            SELECT c.id, c.name, c.movie, c.rarity, c.file_id, c.file_type,
                   uc.is_favorite, uc.caught_at
            FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            WHERE uc.user_id=?
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """, (user_id, per_page, offset)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def count_user_cards(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM user_cards WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return row[0]

async def user_has_card(user_id: int, card_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM user_cards WHERE user_id=? AND card_id=?", (user_id, card_id)
        ) as cur:
            return await cur.fetchone() is not None

async def set_favorite(user_id: int, card_id: int) -> bool:
    """Set card as favorite. Returns False if card not owned."""
    has = await user_has_card(user_id, card_id)
    if not has:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE user_cards SET is_favorite=0 WHERE user_id=?", (user_id,)
        )
        await db.execute(
            "UPDATE user_cards SET is_favorite=1 WHERE user_id=? AND card_id=?",
            (user_id, card_id)
        )
        await db.commit()
    return True

async def remove_favorite(user_id: int, card_id: int) -> bool:
    has = await user_has_card(user_id, card_id)
    if not has:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE user_cards SET is_favorite=0 WHERE user_id=? AND card_id=?",
            (user_id, card_id)
        )
        await db.commit()
    return True

async def get_favorite_card(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT c.* FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            WHERE uc.user_id=? AND uc.is_favorite=1
        """, (user_id,)) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

async def user_has_rarity(user_id: int, rarity: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT 1 FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            WHERE uc.user_id=? AND c.rarity=?
        """, (user_id, rarity)) as cur:
            return await cur.fetchone() is not None

# ─────────────────────────────────────────────
# SHOP & INVENTORY
# ─────────────────────────────────────────────
async def init_shop(items: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for item in items:
            await db.execute("""
                INSERT OR IGNORE INTO shop_items
                (item_key, name, description, price, effect, duration)
                VALUES (?,?,?,?,?,?)
            """, (item["id"], item["name"], item["desc"], item["price"],
                  item["effect"], item["duration"]))
        await db.commit()

async def get_shop_items() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM shop_items WHERE is_active=1 ORDER BY price"
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def get_shop_item(item_key: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM shop_items WHERE item_key=? AND is_active=1", (item_key,)
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

async def buy_item(user_id: int, item_key: str) -> Dict:
    """Returns {success, message}"""
    item = await get_shop_item(item_key)
    if not item:
        return {"success": False, "message": "Item not found"}
    user = await get_user(user_id)
    if not user:
        return {"success": False, "message": "User not found"}
    if user["coins"] < item["price"]:
        return {"success": False, "message": f"Not enough coins! Need {item['price']:,} coins."}

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET coins = coins - ?, total_spent = total_spent + ? WHERE user_id=?",
            (item["price"], item["price"], user_id)
        )
        await db.execute("""
            INSERT INTO user_inventory (user_id, item_key, quantity)
            VALUES (?,?,1)
            ON CONFLICT DO UPDATE SET quantity = quantity + 1
        """, (user_id, item_key))
        await db.execute(
            "INSERT INTO transactions (from_user, to_user, amount, tx_type, note) VALUES (?,0,?,?,?)",
            (user_id, item["price"], "shop_buy", f"Bought {item['name']}")
        )
        await db.commit()
    return {"success": True, "message": f"✅ Purchased **{item['name']}**!", "item": item}

async def get_user_inventory(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT ui.item_key, ui.quantity, ui.expires_at,
                   si.name, si.description, si.effect
            FROM user_inventory ui
            JOIN shop_items si ON ui.item_key = si.item_key
            WHERE ui.user_id=? AND ui.quantity > 0
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# SOCIAL: FRIENDS, MARRIAGE
# ─────────────────────────────────────────────
async def add_friend(user_id: int, friend_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?,?)",
                (user_id, friend_id)
            )
            await db.execute(
                "INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?,?)",
                (friend_id, user_id)
            )
            await db.commit()
        return True
    except Exception:
        return False

async def get_friends(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.user_id, u.username, u.first_name, u.level, u.active_title
            FROM friends f JOIN users u ON f.friend_id = u.user_id
            WHERE f.user_id=?
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def are_friends(user_id: int, friend_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM friends WHERE user_id=? AND friend_id=?", (user_id, friend_id)
        ) as cur:
            return await cur.fetchone() is not None

async def marry(user1_id: int, user2_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET married_to=? WHERE user_id=?", (user2_id, user1_id)
        )
        await db.execute(
            "UPDATE users SET married_to=? WHERE user_id=?", (user1_id, user2_id)
        )
        await db.commit()
    return True

async def divorce(user_id: int) -> Optional[int]:
    user = await get_user(user_id)
    if not user or not user["married_to"]:
        return None
    partner_id = user["married_to"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET married_to=NULL WHERE user_id=?", (user_id,))
        await db.execute("UPDATE users SET married_to=NULL WHERE user_id=?", (partner_id,))
        await db.commit()
    return partner_id

async def give_coins(from_id: int, to_id: int, amount: int) -> Dict:
    sender = await get_user(from_id)
    if not sender:
        return {"success": False, "message": "Sender not found"}
    if sender["coins"] < amount:
        return {"success": False, "message": f"Insufficient coins! You have {sender['coins']:,}"}
    if amount <= 0:
        return {"success": False, "message": "Amount must be positive"}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (amount, from_id))
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, to_id))
        await db.execute(
            "INSERT INTO transactions (from_user, to_user, amount, tx_type, note) VALUES (?,?,?,?,?)",
            (from_id, to_id, amount, "transfer", f"Coin gift")
        )
        await db.commit()
    return {"success": True}

# ─────────────────────────────────────────────
# LEADERBOARD
# ─────────────────────────────────────────────
async def get_top_users(limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, first_name, coins, level, active_title "
            "FROM users ORDER BY coins DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def get_weekly_top(limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM weekly_board ORDER BY weekly_coins DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def reset_weekly_board():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM weekly_board")
        await db.commit()

# ─────────────────────────────────────────────
# MISSIONS
# ─────────────────────────────────────────────
async def init_missions(daily_list: list, weekly_list: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for m in daily_list:
            await db.execute("""
                INSERT OR IGNORE INTO missions
                (mission_key, name, description, mission_type, requirement, reward, period)
                VALUES (?,?,?,?,?,?,?)
            """, (m["id"], m["name"], m["desc"], m["type"], m["req"], m["reward"], "daily"))
        for m in weekly_list:
            await db.execute("""
                INSERT OR IGNORE INTO missions
                (mission_key, name, description, mission_type, requirement, reward, period)
                VALUES (?,?,?,?,?,?,?)
            """, (m["id"], m["name"], m["desc"], m["type"], m["req"], m["reward"], "weekly"))
        await db.commit()

async def get_user_missions(user_id: int) -> List[Dict]:
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    today_end = (now.date() + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    week_end  = (now.date() + timedelta(days=(7 - now.weekday()))).strftime("%Y-%m-%d 00:00:00")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = []
        async with db.execute("SELECT * FROM missions") as cur:
            missions = await cur.fetchall()
        for m in missions:
            m = dict(m)
            reset_at = today_end if m["period"] == "daily" else week_end
            async with db.execute("""
                INSERT OR IGNORE INTO user_missions (user_id, mission_key, reset_at)
                VALUES (?,?,?)
            """, (user_id, m["mission_key"], reset_at)) as _:
                pass
            await db.commit()
            async with db.execute(
                "SELECT * FROM user_missions WHERE user_id=? AND mission_key=?",
                (user_id, m["mission_key"])
            ) as cur2:
                um = await cur2.fetchone()
            if um:
                m.update(dict(um))
                rows.append(m)
        return rows

async def update_mission_progress(user_id: int, mission_type: str, delta: int = 1):
    from datetime import datetime
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM missions WHERE mission_type=?", (mission_type,)
        ) as cur:
            missions = [dict(r) for r in await cur.fetchall()]
        rewards = []
        for m in missions:
            async with db.execute(
                "SELECT * FROM user_missions WHERE user_id=? AND mission_key=?",
                (user_id, m["mission_key"])
            ) as cur2:
                um = await cur2.fetchone()
            if um:
                um = dict(um)
                # Check if expired
                if um["reset_at"] and now > um["reset_at"]:
                    await db.execute(
                        "UPDATE user_missions SET progress=0, completed=0 WHERE user_id=? AND mission_key=?",
                        (user_id, m["mission_key"])
                    )
                    um["progress"] = 0
                    um["completed"] = 0
                if not um["completed"]:
                    new_prog = min(um["progress"] + delta, m["requirement"])
                    completed = 1 if new_prog >= m["requirement"] else 0
                    await db.execute(
                        "UPDATE user_missions SET progress=?, completed=? WHERE user_id=? AND mission_key=?",
                        (new_prog, completed, user_id, m["mission_key"])
                    )
                    if completed and not um["completed"]:
                        rewards.append({"mission": m["name"], "reward": m["reward"]})
        await db.commit()
        return rewards

# ─────────────────────────────────────────────
# ACHIEVEMENTS
# ─────────────────────────────────────────────
async def init_achievements(ach_list: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for a in ach_list:
            await db.execute("""
                INSERT OR IGNORE INTO achievements
                (ach_key, name, description, badge, req_type, req_value)
                VALUES (?,?,?,?,?,?)
            """, (a["id"], a["name"], a["desc"], a["badge"], a["req_type"], a["req_value"]))
        await db.commit()

async def check_achievements(user_id: int) -> List[Dict]:
    """Check and grant new achievements. Returns list of newly earned."""
    user = await get_user(user_id)
    if not user:
        return []
    new_earned = []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT ach_key FROM user_achievements WHERE user_id=?", (user_id,)
        ) as cur:
            already = {r[0] for r in await cur.fetchall()}
        async with db.execute("SELECT * FROM achievements") as cur:
            all_achs = [dict(r) for r in await cur.fetchall()]

        for a in all_achs:
            if a["ach_key"] in already:
                continue
            earned = False
            rt, rv = a["req_type"], a["req_value"]
            if rt == "catch_count"   and user["total_caught"] >= rv:     earned = True
            elif rt == "coins"       and user["coins"] >= rv:             earned = True
            elif rt == "level"       and user["level"] >= rv:             earned = True
            elif rt == "streak"      and user["streak"] >= rv:            earned = True
            elif rt == "jackpot"     and user["jackpots"] >= rv:          earned = True
            elif rt == "combo"       and user["best_combo"] >= rv:        earned = True
            elif rt == "married"     and user.get("married_to") is not None: earned = True
            elif rt == "days_played" and user["days_played"] >= rv:       earned = True
            elif rt == "catch_legendary":
                has_leg = await user_has_rarity(user_id, "Legendary")
                earned = has_leg
            elif rt == "friends":
                friends = await get_friends(user_id)
                earned  = len(friends) >= rv
            elif rt == "all_rarities":
                all_r   = all(await user_has_rarity(user_id, r)
                               for r in ["Common","Uncommon","Rare","Epic","Legendary"])
                earned  = all_r

            if earned:
                await db.execute(
                    "INSERT OR IGNORE INTO user_achievements (user_id, ach_key) VALUES (?,?)",
                    (user_id, a["ach_key"])
                )
                new_earned.append(a)
        await db.commit()
    return new_earned

async def get_user_achievements(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT a.*, ua.earned_at
            FROM user_achievements ua
            JOIN achievements a ON ua.ach_key = a.ach_key
            WHERE ua.user_id=?
            ORDER BY ua.earned_at
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# TITLES
# ─────────────────────────────────────────────
async def init_titles(title_list: list):
    async with aiosqlite.connect(DB_PATH) as db:
        for t in title_list:
            await db.execute("""
                INSERT OR IGNORE INTO titles (title_key, name, description, condition, emoji)
                VALUES (?,?,?,?,?)
            """, (t["id"], t["name"], t["desc"], t["condition"], t["emoji"]))
        await db.commit()

async def get_user_titles(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT t.*, ut.earned_at
            FROM user_titles ut JOIN titles t ON ut.title_key = t.title_key
            WHERE ut.user_id=?
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def grant_title(user_id: int, title_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_titles (user_id, title_key) VALUES (?,?)",
            (user_id, title_key)
        )
        await db.commit()

async def check_titles(user_id: int) -> List[Dict]:
    user = await get_user(user_id)
    if not user:
        return []
    new_titles = []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT title_key FROM user_titles WHERE user_id=?", (user_id,)
        ) as cur:
            already = {r[0] for r in await cur.fetchall()}
        async with db.execute("SELECT * FROM titles") as cur:
            all_titles = [dict(r) for r in await cur.fetchall()]

        for t in all_titles:
            if t["title_key"] in already:
                continue
            cond = t["condition"]
            earned = False
            if cond == "default":                                   earned = True
            elif cond == "catch_20"   and user["total_caught"] >= 20: earned = True
            elif cond == "own_legendary":
                earned = await user_has_rarity(user_id, "Legendary")
            elif cond == "coins_100k" and user["coins"] >= 100000:  earned = True
            elif cond == "married"    and user.get("married_to"):    earned = True
            elif cond == "combo_15"   and user["best_combo"] >= 15:  earned = True
            elif cond == "level_25"   and user["level"] >= 25:       earned = True
            elif cond == "streak_30"  and user["streak"] >= 30:      earned = True
            elif cond == "slots_win_10k" and user["slots_wins"] >= 10000: earned = True

            if earned:
                await db.execute(
                    "INSERT OR IGNORE INTO user_titles (user_id, title_key) VALUES (?,?)",
                    (user_id, t["title_key"])
                )
                new_titles.append(t)
        await db.commit()
    return new_titles

# ─────────────────────────────────────────────
# SUDO / ADMIN
# ─────────────────────────────────────────────
async def is_sudo(user_id: int) -> bool:
    from config import OWNER_ID
    if user_id == OWNER_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM sudo_admins WHERE user_id=?", (user_id,)
        ) as cur:
            return await cur.fetchone() is not None

async def add_sudo(user_id: int, username: str, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO sudo_admins (user_id, username, added_by) VALUES (?,?,?)",
            (user_id, username, added_by)
        )
        await db.commit()

async def get_sudo_list() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sudo_admins ORDER BY added_at") as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# DROP SETTINGS
# ─────────────────────────────────────────────
async def get_drop_rate() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT current_rate FROM drop_settings ORDER BY id DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 1.0

async def set_drop_rate(rate: float, set_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE drop_settings SET current_rate=?, set_by=?, updated_at=datetime('now')",
            (rate, set_by)
        )
        await db.commit()

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────
async def get_server_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users")   as c: total_users   = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM cards")   as c: total_cards   = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM user_cards") as c: total_caught = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(coins) FROM users") as c: total_coins   = (await c.fetchone())[0] or 0
        async with db.execute("SELECT COUNT(*) FROM transactions") as c: total_txs = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM sudo_admins") as c: total_sudos = (await c.fetchone())[0]
    return {
        "total_users":   total_users,
        "total_cards":   total_cards,
        "total_caught":  total_caught,
        "total_coins":   total_coins,
        "total_txs":     total_txs,
        "total_sudos":   total_sudos,
    }

async def get_all_users() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────────
async def audit(admin_id: int, action: str, target: str, details: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audit_log (admin_id, action, target, details) VALUES (?,?,?,?)",
            (admin_id, action, target, details)
        )
        await db.commit()

# ─────────────────────────────────────────────
# DATABASE NUKE (Owner only)
# ─────────────────────────────────────────────
async def clear_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users")
        await db.execute("DELETE FROM user_cards")
        await db.execute("DELETE FROM user_inventory")
        await db.execute("DELETE FROM user_missions")
        await db.execute("DELETE FROM user_achievements")
        await db.execute("DELETE FROM user_titles")
        await db.execute("DELETE FROM friends")
        await db.execute("DELETE FROM transactions")
        await db.execute("DELETE FROM weekly_board")
        await db.commit()

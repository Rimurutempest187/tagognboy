# ════════════════════════════════════════════
# 🃏 Card Collection Bot — Utility Helpers
# ════════════════════════════════════════════
import random
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from config import LEVEL_XP_REQUIREMENTS, RARITY_CONFIG, TITLES


# ── Progress Bar ──────────────────────────────
def make_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum == 0:
        return "▓" * length
    filled = int((current / maximum) * length)
    return "▓" * filled + "░" * (length - filled)


# ── XP Bar ───────────────────────────────────
def xp_bar(level: int, xp: int) -> str:
    if level >= len(LEVEL_XP_REQUIREMENTS) - 1:
        return f"{'▓' * 10} MAX"
    curr_need = LEVEL_XP_REQUIREMENTS[level - 1] if level > 1 else 0
    next_need = LEVEL_XP_REQUIREMENTS[level]
    progress  = xp - curr_need
    total     = next_need - curr_need
    bar       = make_bar(progress, total, 10)
    return f"{bar} {progress:,}/{total:,}"


# ── Name Mention ─────────────────────────────
def mention(user: Dict) -> str:
    name = user.get("first_name") or user.get("username") or f"User {user['user_id']}"
    return f"<a href='tg://user?id={user['user_id']}'>{name}</a>"


def safe_name(user) -> str:
    if hasattr(user, "first_name"):
        return user.first_name or user.username or str(user.id)
    return user.get("first_name") or user.get("username") or str(user.get("user_id", "?"))


# ── Rarity Emoji ─────────────────────────────
def rarity_stars(rarity: str) -> str:
    star_map = {
        "Common":    "⚪",
        "Uncommon":  "🟢",
        "Rare":      "🔵",
        "Epic":      "🟣",
        "Legendary": "🟡⭐",
    }
    return star_map.get(rarity, "⚪")


# ── Slots Engine ─────────────────────────────
def spin_slots() -> Dict:
    from config import SLOTS_SYMBOLS, SLOTS_WEIGHTS
    reels = random.choices(SLOTS_SYMBOLS, weights=SLOTS_WEIGHTS, k=3)
    if reels[0] == reels[1] == reels[2]:
        if reels[0] == "7️⃣":
            result = "jackpot"
            multiplier = 50
        elif reels[0] == "💎":
            result = "super"
            multiplier = 15
        elif reels[0] == "⭐":
            result = "mega"
            multiplier = 8
        else:
            result = "triple"
            multiplier = 4
    elif reels[0] == reels[1] or reels[1] == reels[2]:
        result = "pair"
        multiplier = 1.5
    else:
        result = "lose"
        multiplier = 0

    return {
        "reels":      reels,
        "result":     result,
        "multiplier": multiplier,
        "display":    " | ".join(reels),
    }


def slots_animation_frames(reels: List[str]) -> List[str]:
    """Return animation frames for slot result."""
    syms = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
    frames = []
    for _ in range(3):
        r = [random.choice(syms) for _ in range(3)]
        frames.append(f"🎰 | {r[0]} | {r[1]} | {r[2]} |")
    frames.append(f"🎰 | {reels[0]} | {reels[1]} | {reels[2]} |")
    return frames


# ── Basket Game Engine ────────────────────────
def basket_shot(combo: int, luck_bonus: float = 0.0) -> Dict:
    """Returns shot result. Higher combo = slight difficulty."""
    base_chance = max(0.45 - (combo * 0.01), 0.30) + luck_bonus
    hit = random.random() < base_chance
    pts = 2
    if hit and combo >= 5:
        pts = 3 if random.random() < 0.3 else 2   # chance of 3-pointer
    return {"hit": hit, "points": pts if hit else 0}


def basket_animation(hit: bool) -> str:
    if hit:
        return random.choice(["🏀→🏀→🎯✅", "🏀💨🎯✅", "🏀🌀🗑️✅"])
    else:
        return random.choice(["🏀→💨❌", "🏀🔄💨❌", "🏀→🚫❌"])


# ── Wheel Engine ─────────────────────────────
def spin_wheel() -> Dict:
    from config import WHEEL_PRIZES
    weights = [p["weight"] for p in WHEEL_PRIZES]
    prize   = random.choices(WHEEL_PRIZES, weights=weights, k=1)[0]
    return prize


def wheel_animation() -> List[str]:
    emojis = ["🎡", "🌀", "💫", "✨", "🎯"]
    frames = []
    for i in range(4):
        frames.append(random.choice(emojis) + " Spinning...")
    return frames


# ── Catch Engine ─────────────────────────────
def calculate_catch_chance(rarity: str, drop_rate: float, boost: float = 0.0) -> float:
    base = RARITY_CONFIG.get(rarity, RARITY_CONFIG["Common"])["catch_rate"]
    return min(base * drop_rate + boost, 0.98)


def attempt_catch(chance: float) -> bool:
    return random.random() < chance


# ── Daily Streak ─────────────────────────────
def calc_daily_bonus(streak: int) -> int:
    from config import DAILY_BONUS_BASE, MAX_STREAK_MULTIPLIER
    mult = min(streak, MAX_STREAK_MULTIPLIER)
    return DAILY_BONUS_BASE + (DAILY_BONUS_BASE * (mult - 1) // 2)


# ── Pagination ───────────────────────────────
def paginate(items: list, page: int, per_page: int = 10):
    start = (page - 1) * per_page
    end   = start + per_page
    return items[start:end], len(items)


# ── Format Numbers ────────────────────────────
def fmt_coins(n: int) -> str:
    return f"{n:,} 🪙"


# ── Date helpers ─────────────────────────────
def today_str() -> str:
    return date.today().isoformat()


def is_new_day(last_date_str: Optional[str]) -> bool:
    if not last_date_str:
        return True
    try:
        last = date.fromisoformat(last_date_str[:10])
        return date.today() > last
    except Exception:
        return True


# ── Rarity Weighted Random ────────────────────
def weighted_rarity() -> str:
    rarities = list(RARITY_CONFIG.keys())
    weights  = [80, 50, 25, 10, 3]   # Common, Uncommon, Rare, Epic, Legendary
    return random.choices(rarities, weights=weights, k=1)[0]


# ── Chunk long texts ─────────────────────────
def split_text(text: str, limit: int = 4000) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)
    return chunks

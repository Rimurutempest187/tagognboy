# ════════════════════════════════════════════
# 🃏 Card Character Collection Bot - Config
# ════════════════════════════════════════════
import os
from dotenv import load_dotenv

load_dotenv()

# ── Core Settings ──────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
DB_PATH: str = os.getenv("DB_PATH", "cardgame.db")
BACKUP_DIR: str = os.getenv("BACKUP_DIR", "backups")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Economy Settings ──────────────────────
STARTING_COINS: int = int(os.getenv("STARTING_COINS", "1000"))
DAILY_BONUS_BASE: int = int(os.getenv("DAILY_BONUS_BASE", "200"))
MAX_STREAK_MULTIPLIER: int = int(os.getenv("MAX_STREAK_MULTIPLIER", "5"))

# ── Game Settings ─────────────────────────
SLOTS_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
SLOTS_WEIGHTS  = [30, 25, 20, 12, 8, 4, 1]

WHEEL_PRIZES = [
    {"name": "100 Coins",   "value": 100,   "type": "coins",  "weight": 30},
    {"name": "250 Coins",   "value": 250,   "type": "coins",  "weight": 25},
    {"name": "500 Coins",   "value": 500,   "type": "coins",  "weight": 15},
    {"name": "1000 Coins",  "value": 1000,  "type": "coins",  "weight": 10},
    {"name": "XP Boost",    "value": 200,   "type": "xp",     "weight": 8},
    {"name": "Rare Card",   "value": 1,     "type": "card",   "weight": 5},
    {"name": "2000 Coins",  "value": 2000,  "type": "coins",  "weight": 4},
    {"name": "JACKPOT 🎰",  "value": 5000,  "type": "coins",  "weight": 2},
    {"name": "Lucky Item",  "value": 1,     "type": "item",   "weight": 1},
]

# ── Card Rarity Settings ─────────────────
RARITY_CONFIG = {
    "Common":    {"emoji": "⚪", "catch_rate": 0.85, "color": "grey",   "xp_reward": 10},
    "Uncommon":  {"emoji": "🟢", "catch_rate": 0.65, "color": "green",  "xp_reward": 20},
    "Rare":      {"emoji": "🔵", "catch_rate": 0.40, "color": "blue",   "xp_reward": 40},
    "Epic":      {"emoji": "🟣", "catch_rate": 0.20, "color": "purple", "xp_reward": 80},
    "Legendary": {"emoji": "🟡", "catch_rate": 0.08, "color": "gold",   "xp_reward": 150},
}

# ── Level System ─────────────────────────
LEVEL_XP_REQUIREMENTS = [
    0, 100, 250, 500, 900, 1500, 2300, 3300, 4500, 6000,
    8000, 10500, 13500, 17000, 21000, 25500, 30500, 36000,
    42000, 49000, 57000, 66000, 76000, 87000, 99000, 112000
]

# ── Mission Definitions ──────────────────
DAILY_MISSIONS = [
    {"id": "dm1", "name": "Card Hunter",    "desc": "Catch 3 cards",          "req": 3,   "type": "catch",  "reward": 150},
    {"id": "dm2", "name": "Coin Collector", "desc": "Play slots 5 times",     "req": 5,   "type": "slots",  "reward": 200},
    {"id": "dm3", "name": "Hooper",         "desc": "Play basket 3 times",    "req": 3,   "type": "basket", "reward": 180},
    {"id": "dm4", "name": "Socialite",      "desc": "Give coins to a friend", "req": 1,   "type": "give",   "reward": 100},
    {"id": "dm5", "name": "Spinner",        "desc": "Spin the wheel 2 times", "req": 2,   "type": "wheel",  "reward": 120},
]

WEEKLY_MISSIONS = [
    {"id": "wm1", "name": "Collector",    "desc": "Catch 20 cards",         "req": 20,  "type": "catch",  "reward": 1500},
    {"id": "wm2", "name": "High Roller",  "desc": "Play slots 30 times",    "req": 30,  "type": "slots",  "reward": 2000},
    {"id": "wm3", "name": "MVP",          "desc": "Score 100 in basket",    "req": 100, "type": "bscore", "reward": 2500},
    {"id": "wm4", "name": "Generous",     "desc": "Give 5000 coins total",  "req": 5000,"type": "give",   "reward": 3000},
    {"id": "wm5", "name": "Veteran",      "desc": "Log in 7 days in a row", "req": 7,   "type": "streak", "reward": 1800},
]

# ── Achievement Definitions ──────────────
ACHIEVEMENTS = [
    {"id": "ach1",  "name": "First Steps",    "desc": "Catch your first card",         "badge": "🎯", "req_type": "catch_count",   "req_value": 1},
    {"id": "ach2",  "name": "Collector I",    "desc": "Catch 10 cards",                "badge": "📦", "req_type": "catch_count",   "req_value": 10},
    {"id": "ach3",  "name": "Collector II",   "desc": "Catch 50 cards",                "badge": "🗃️", "req_type": "catch_count",   "req_value": 50},
    {"id": "ach4",  "name": "Legendary!",     "desc": "Catch a Legendary card",        "badge": "⚡", "req_type": "catch_legendary","req_value": 1},
    {"id": "ach5",  "name": "Lucky Sevens",   "desc": "Hit jackpot in slots",          "badge": "🎰", "req_type": "jackpot",        "req_value": 1},
    {"id": "ach6",  "name": "Rich!",          "desc": "Have 10,000 coins",             "badge": "💰", "req_type": "coins",          "req_value": 10000},
    {"id": "ach7",  "name": "Millionaire",    "desc": "Have 100,000 coins",            "badge": "💎", "req_type": "coins",          "req_value": 100000},
    {"id": "ach8",  "name": "Streak Master",  "desc": "Reach 7-day streak",            "badge": "🔥", "req_type": "streak",         "req_value": 7},
    {"id": "ach9",  "name": "Level 10",       "desc": "Reach Level 10",                "badge": "🌟", "req_type": "level",          "req_value": 10},
    {"id": "ach10", "name": "Max Level",      "desc": "Reach Level 25",                "badge": "👑", "req_type": "level",          "req_value": 25},
    {"id": "ach11", "name": "Lovebird",       "desc": "Get married",                   "badge": "💍", "req_type": "married",        "req_value": 1},
    {"id": "ach12", "name": "Social Bee",     "desc": "Have 5 friends",                "badge": "🤝", "req_type": "friends",        "req_value": 5},
    {"id": "ach13", "name": "Combo King",     "desc": "Hit 10-combo in basket",        "badge": "🏀", "req_type": "combo",          "req_value": 10},
    {"id": "ach14", "name": "Veteran",        "desc": "Play for 30 days",              "badge": "🎖️","req_type": "days_played",    "req_value": 30},
    {"id": "ach15", "name": "Card Master",    "desc": "Collect all rarities",          "badge": "🃏", "req_type": "all_rarities",   "req_value": 1},
]

# ── Title Definitions ─────────────────────
TITLES = [
    {"id": "t1",  "name": "Novice",        "desc": "Starting Title",             "condition": "default",       "emoji": "🌱"},
    {"id": "t2",  "name": "Card Hunter",   "desc": "Catch 20 cards",             "condition": "catch_20",       "emoji": "🎯"},
    {"id": "t3",  "name": "High Roller",   "desc": "Win 10,000 coins in slots",  "condition": "slots_win_10k",  "emoji": "🎰"},
    {"id": "t4",  "name": "Legend Holder", "desc": "Own a Legendary card",       "condition": "own_legendary",  "emoji": "⚡"},
    {"id": "t5",  "name": "Millionaire",   "desc": "Accumulate 100K coins",      "condition": "coins_100k",     "emoji": "💎"},
    {"id": "t6",  "name": "Lovebird",      "desc": "Get married",                "condition": "married",        "emoji": "💍"},
    {"id": "t7",  "name": "Combo Master",  "desc": "Hit 15+ combo in basket",    "condition": "combo_15",       "emoji": "🏀"},
    {"id": "t8",  "name": "Max Level",     "desc": "Reach Level 25",             "condition": "level_25",       "emoji": "👑"},
    {"id": "t9",  "name": "Streak God",    "desc": "30-day login streak",        "condition": "streak_30",      "emoji": "🔥"},
    {"id": "t10", "name": "Completionist", "desc": "Complete all achievements",  "condition": "all_achievements","emoji": "🏆"},
]

# ── Shop Items ────────────────────────────
DEFAULT_SHOP_ITEMS = [
    {"id": "s1", "name": "Catch Boost",    "desc": "+20% catch rate for 1 hour",    "price": 500,  "effect": "catch_boost_1h",  "duration": 3600},
    {"id": "s2", "name": "XP Booster",     "desc": "Double XP for 2 hours",         "price": 800,  "effect": "xp_boost_2h",     "duration": 7200},
    {"id": "s3", "name": "Lucky Charm",    "desc": "+15% slots win rate for 30min", "price": 400,  "effect": "slots_luck_30m",  "duration": 1800},
    {"id": "s4", "name": "Coin Rain",      "desc": "Get 1000 coins instantly",      "price": 750,  "effect": "instant_1000",    "duration": 0},
    {"id": "s5", "name": "Dupe Shield",    "desc": "Avoid duplicate catches x5",    "price": 600,  "effect": "dupe_shield_5",   "duration": 0},
    {"id": "s6", "name": "Mega Ball",      "desc": "+30% catch rate for 1 hour",    "price": 1200, "effect": "catch_boost_2h",  "duration": 7200},
    {"id": "s7", "name": "Slot Frenzy",    "desc": "2x slots payout for 30 min",    "price": 1000, "effect": "slots_double_30m", "duration": 1800},
    {"id": "s8", "name": "VIP Badge",      "desc": "Show VIP status for 1 day",     "price": 2000, "effect": "vip_badge_1d",    "duration": 86400},
]

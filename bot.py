#!/usr/bin/env python3
# bot.py - Single-file Card Collection Telegram Bot (python-telegram-bot 20.x)
# Version: fixed single-file runnable example

import asyncio
import logging
import os
import sqlite3
import sys
import json
import random
from datetime import datetime, date, timedelta, time as dtime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# -----------------------
# Configuration
# -----------------------
load_dotenv()  # loads .env if present

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except Exception:
    OWNER_ID = 0

DB_FILE = os.getenv("DB_FILE", "cardbot.db")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# default shop items and cards (simple examples)
DEFAULT_SHOP_ITEMS = [
    {"item_key": "lucky_ticket", "name": "Lucky Ticket", "price": 500, "desc": "Use to increase catch chance"},
    {"item_key": "card_pack", "name": "Card Pack", "price": 1200, "desc": "Gives 3 random cards"},
]

# initial cards (id, name, rarity)
CARDS = [
    (1, "Red Ranger", "common"),
    (2, "Blue Mage", "common"),
    (3, "Silver Knight", "rare"),
    (4, "Golden Dragon", "epic"),
    (5, "Celestial Empress", "legendary"),
]

# -----------------------
# Logging
# -----------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# -----------------------
# Database helpers
# -----------------------
def get_conn():
    conn = sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they do not exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        coins INTEGER DEFAULT 1000,
        last_daily TIMESTAMP NULL,
        active_title TEXT DEFAULT NULL,
        favorite_card INTEGER DEFAULT NULL,
        married_to INTEGER DEFAULT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        card_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        rarity TEXT NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        card_id INTEGER NOT NULL,
        obtained_at TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(card_id) REFERENCES cards(card_id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS shop (
        item_key TEXT PRIMARY KEY,
        name TEXT,
        price INTEGER,
        description TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sudo_list (
        user_id INTEGER PRIMARY KEY
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS weekly_board (
        user_id INTEGER PRIMARY KEY,
        score INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

def init_defaults():
    conn = get_conn()
    cur = conn.cursor()
    # Insert default cards if missing
    for cid, name, rarity in CARDS:
        cur.execute("INSERT OR IGNORE INTO cards(card_id, name, rarity) VALUES (?, ?, ?)", (cid, name, rarity))
    # Insert default shop items
    for item in DEFAULT_SHOP_ITEMS:
        cur.execute(
            "INSERT OR IGNORE INTO shop(item_key, name, price, description) VALUES (?, ?, ?, ?)",
            (item["item_key"], item["name"], item["price"], item.get("desc", "")),
        )
    conn.commit()
    conn.close()

# -----------------------
# DB convenience async wrappers
# -----------------------
async def db_get_or_create_user(user_id: int, username: str, first_name: str) -> Dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row:
        user = dict(row)
    else:
        cur.execute(
            "INSERT INTO users(user_id, username, first_name, coins) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, 1000),
        )
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = dict(cur.fetchone())
    conn.close()
    return user

async def db_is_sudo(user_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sudo_list WHERE user_id = ?", (user_id,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok

async def db_add_sudo(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO sudo_list(user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

async def db_list_sudo() -> List[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM sudo_list")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

async def db_add_coins(user_id: int, amount: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

async def db_get_user(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

async def db_update_user_field(user_id: int, field: str, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

async def db_get_shop_items() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shop")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

async def db_buy_item(user_id: int, item_key: str) -> Tuple[bool, str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT price, name FROM shop WHERE item_key = ?", (item_key,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Item not found."
    price = row["price"]
    name = row["name"]
    cur.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    cur_user = cur.fetchone()
    if not cur_user:
        conn.close()
        return False, "User not found."
    if cur_user["coins"] < price:
        conn.close()
        return False, "Not enough coins."
    # deduct
    cur.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, user_id))
    conn.commit()
    conn.close()
    return True, f"Bought {name} for {price} coins."

async def db_add_inventory_card(user_id: int, card_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO inventory(user_id, card_id, obtained_at) VALUES (?, ?, ?)", (user_id, card_id, datetime.utcnow()))
    conn.commit()
    conn.close()

async def db_get_user_inventory(user_id: int) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""SELECT i.id, i.card_id, i.obtained_at, c.name, c.rarity
                   FROM inventory i JOIN cards c ON i.card_id = c.card_id
                   WHERE i.user_id = ? ORDER BY i.obtained_at DESC""", (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

async def db_get_random_card_by_rarity(rarity: Optional[str] = None) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    if rarity:
        cur.execute("SELECT * FROM cards WHERE rarity = ? ORDER BY RANDOM() LIMIT 1", (rarity,))
    else:
        cur.execute("SELECT * FROM cards ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

async def db_get_weekly_top(limit: int = 10) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT u.user_id, u.username, wb.score FROM weekly_board wb
    JOIN users u ON wb.user_id = u.user_id
    ORDER BY wb.score DESC LIMIT ?""", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

async def db_add_weekly_score(user_id: int, add: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO weekly_board(user_id, score) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET score = score + ?", (user_id, add, add))
    conn.commit()
    conn.close()

async def db_reset_weekly_board():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM weekly_board")
    conn.commit()
    conn.close()

# -----------------------
# Utilities
# -----------------------
def is_owner(user_id: int) -> bool:
    return OWNER_ID != 0 and user_id == OWNER_ID

async def is_admin_or_owner(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    return await db_is_sudo(user_id)

# -----------------------
# Handlers
# -----------------------
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await db_get_or_create_user(u.id, u.username or "", u.first_name or "")
    text = (
        "╔══════════════════════════╗\n"
        "   🃏 <b>CARD COLLECTION BOT</b>\n"
        "╚══════════════════════════╝\n\n"
        f"Welcome, <b>{u.first_name}</b>! 👋\n\n"
        "🎮 <b>Get Started:</b>\n"
        "  /daily  — Claim daily bonus\n"
        "  /catch  — Catch a random card\n"
        "  /balance — View your profile\n\n"
        "🃏 <b>Cards:</b>\n"
        "  /catch <name> · /inventory · /set <id>\n\n"
        "🎮 <b>Games:</b>\n"
        "  /slots · /basket · /wheel\n\n"
        "📊 <b>Progress:</b>\n"
        "  /missions · /achievements · /top\n\n"
        "💡 Use /help for all commands!"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = await db_is_sudo(user_id)
    text = (
        "╔══════════════════════════╗\n"
        "  📖 <b>COMMAND LIST</b>\n"
        "╚══════════════════════════╝\n\n"
        "👤 <b>Player</b>\n"
        "/balance — Profile & stats\n"
        "/daily — Daily bonus\n"
        "/shop — Item shop\n"
        "/buy <item_key> — Buy item\n\n"
        "🎮 <b>Games</b>\n"
        "/slots <amount> — Slot machine\n"
        "/basket <amount> — Basketball\n"
        "/wheel <amount> — Wheel of fortune\n\n"
        "🎴 <b>Cards</b>\n"
        "/catch [name] — Catch a card\n"
        "/inventory — View collection\n"
        "/set <id> — Set favorite card\n"
        "/removeset — Remove favorite\n\n"
        "👥 <b>Social</b>\n"
        "/givecoin <amt> <@user> — Transfer coins\n"
        "/marry @user — Propose (reply or mention)\n"
        "/divorce — End marriage\n"
        "/friends — Friend list (placeholder)\n\n"
        "📊 <b>Rankings</b>\n"
        "/top — Leaderboard\n"
        "/settitle <title_key> — Set active title\n"
    )
    if is_admin:
        text += (
            "\n🛠 <b>Admin</b>\n"
            "/upload — Upload image card (not implemented)\n"
            "/addcoin <id> <amt> — Give coins\n"
            "/addsudo <id> — Add sudo admin\n"
            "/sudolist — View admins\n"
            "/broadcast <msg> — Message all users\n"
            "/backup — Create DB backup\n"
            "/restore <file> — Restore DB from file\n"
            "/systemcheck — Bot health\n"
        )
    if is_owner(user_id):
        text += "\n👑 <b>Owner</b>\n/allclear — Reset database\n"
    await update.message.reply_text(text, parse_mode="HTML")

# Balance
async def balance_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = await db_get_or_create_user(u.id, u.username or "", u.first_name or "")
    inv = await db_get_user_inventory(u.id)
    fav = user.get("favorite_card")
    fav_name = None
    if fav:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT name FROM cards WHERE card_id = ?", (fav,))
        r = cur.fetchone()
        if r:
            fav_name = r["name"]
        conn.close()
    text = (
        f"👤 <b>{user.get('first_name') or user.get('username')}</b>\n"
        f"💰 <b>Coins:</b> {user.get('coins', 0)}\n"
        f"📦 <b>Cards:</b> {len(inv)}\n"
    )
    if fav_name:
        text += f"\n⭐ <b>Favorite:</b> {fav_name}\n"
    await update.message.reply_text(text, parse_mode="HTML")

# Daily
async def daily_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = await db_get_or_create_user(u.id, u.username or "", u.first_name or "")
    last = user.get("last_daily")
    now = datetime.utcnow()
    allowed = False
    if not last:
        allowed = True
    else:
        last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
        if now - last_dt >= timedelta(hours=20):  # daily ~20h to be lenient
            allowed = True
    if not allowed:
        await update.message.reply_text("❌ You already claimed daily recently. Come back later.")
        return
    reward = random.randint(200, 800)
    await db_add_coins(u.id, reward)
    await db_update_user_field(u.id, "last_daily", now.isoformat())
    await update.message.reply_text(f"🎁 Daily claimed! You received <b>{reward} coins</b>.", parse_mode="HTML")

# Shop & buy
async def shop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    items = await db_get_shop_items()
    if not items:
        await update.message.reply_text("Shop is empty.")
        return
    text = "🏪 <b>Shop Items:</b>\n\n"
    for it in items:
        text += f"{it['item_key']} — {it['name']} — {it['price']} coins\n    {it['description']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def buy_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not ctx.args:
        await update.message.reply_text("Usage: /buy <item_key>")
        return
    item_key = ctx.args[0]
    ok, msg = await db_buy_item(u.id, item_key)
    await update.message.reply_text(msg)

# Catch card
async def catch_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    # simple catch: random rarity roll
    roll = random.random()
    if roll < 0.02:
        rarity = "legendary"
    elif roll < 0.12:
        rarity = "epic"
    elif roll < 0.35:
        rarity = "rare"
    else:
        rarity = "common"
    card = await db_get_random_card_by_rarity(rarity)
    if not card:
        # fallback to any card
        card = await db_get_random_card_by_rarity(None)
    await db_add_inventory_card(u.id, int(card["card_id"]))
    await db_add_weekly_score(u.id, 10)  # reward weekly points
    await update.message.reply_text(
        f"🎴 You caught a card: <b>{card['name']}</b> (rarity: {card['rarity']})",
        parse_mode="HTML",
    )

# Inventory, set favorite, removeset
async def inventory_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    items = await db_get_user_inventory(u.id)
    if not items:
        await update.message.reply_text("You have no cards yet. Use /catch to get cards.")
        return
    text = "<b>Your cards</b>:\n\n"
    for it in items[:50]:
        text += f"#{it['id']} — {it['name']} ({it['rarity']}) — obtained {it['obtained_at']}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def set_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not ctx.args:
        await update.message.reply_text("Usage: /set <card_inventory_id>")
        return
    inv_id = ctx.args[0]
    # validate ownership
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT card_id FROM inventory WHERE id = ? AND user_id = ?", (inv_id, u.id))
    r = cur.fetchone()
    conn.close()
    if not r:
        await update.message.reply_text("That card inventory id doesn't exist or isn't yours.")
        return
    await db_update_user_field(u.id, "favorite_card", r["card_id"])
    await update.message.reply_text("✅ Favorite card set.")

async def removeset_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await db_update_user_field(u.id, "favorite_card", None)
    await update.message.reply_text("✅ Favorite card removed.")

# Simple gambling games
async def slots_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    try:
        amount = int(ctx.args[0]) if ctx.args else 100
    except:
        await update.message.reply_text("Usage: /slots <amount>")
        return
    user = await db_get_user(u.id)
    if not user or user["coins"] < amount:
        await update.message.reply_text("Not enough coins.")
        return
    symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]
    await db_add_coins(u.id, -amount)
    # win conditions
    if res[0] == res[1] == res[2]:
        win = amount * 5
        await db_add_coins(u.id, win)
        await update.message.reply_text(f"{' '.join(res)}\n🎉 JACKPOT! You won {win} coins!")
    elif res[0] == res[1] or res[1] == res[2] or res[0] == res[2]:
        win = int(amount * 1.5)
        await db_add_coins(u.id, win)
        await update.message.reply_text(f"{' '.join(res)}\n🙂 You got a pair. You win {win} coins.")
    else:
        await update.message.reply_text(f"{' '.join(res)}\n😢 You lost {amount} coins.")

async def basket_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    try:
        amount = int(ctx.args[0]) if ctx.args else 100
    except:
        await update.message.reply_text("Usage: /basket <amount>")
        return
    user = await db_get_user(u.id)
    if not user or user["coins"] < amount:
        await update.message.reply_text("Not enough coins.")
        return
    await db_add_coins(u.id, -amount)
    # 50% chance double
    if random.random() < 0.5:
        win = amount * 2
        await db_add_coins(u.id, win)
        await update.message.reply_text(f"🏀 Nice shot! You won {win} coins.")
    else:
        await update.message.reply_text("🏀 Missed! Better luck next time.")

async def wheel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    try:
        amount = int(ctx.args[0]) if ctx.args else 100
    except:
        await update.message.reply_text("Usage: /wheel <amount>")
        return
    user = await db_get_user(u.id)
    if not user or user["coins"] < amount:
        await update.message.reply_text("Not enough coins.")
        return
    await db_add_coins(u.id, -amount)
    sectors = [0, amount//2, amount, amount*2, -amount]  # losses and wins
    result = random.choice(sectors)
    if result > 0:
        await db_add_coins(u.id, result)
        await update.message.reply_text(f"🎡 You won {result} coins!")
    else:
        await update.message.reply_text(f"🎡 You lost {abs(result)} coins.")

# Social
async def givecoin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /givecoin <amount> <@user or id>")
        return
    try:
        amount = int(ctx.args[0])
    except:
        await update.message.reply_text("Invalid amount.")
        return
    target = ctx.args[1]
    # simple: if mention, try to extract id from entities else treat as numeric id
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    else:
        if target.startswith("@"):
            # try to resolve via bot (best effort)
            try:
                member = await ctx.bot.get_chat(target)
                target_id = member.id
            except:
                await update.message.reply_text("Could not resolve username. Use reply or user id.")
                return
        else:
            try:
                target_id = int(target)
            except:
                await update.message.reply_text("Invalid target. Use reply, @username or numeric id.")
                return
    if target_id == u.id:
        await update.message.reply_text("You can't give coins to yourself.")
        return
    sender = await db_get_user(u.id)
    if not sender or sender["coins"] < amount:
        await update.message.reply_text("Not enough coins.")
        return
    await db_add_coins(u.id, -amount)
    await db_add_coins(target_id, amount)
    await update.message.reply_text(f"✅ Sent {amount} coins to <b>{target_id}</b>.", parse_mode="HTML")

async def marry_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    # require replying to the other person or @mention/id
    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif ctx.args:
        try:
            target_id = int(ctx.args[0])
        except:
            await update.message.reply_text("Reply to someone's message or provide their numeric id.")
            return
    else:
        await update.message.reply_text("Reply to someone's message or provide their numeric id.")
        return
    if target_id == u.id:
        await update.message.reply_text("You can't marry yourself.")
        return
    # set married_to in both users
    await db_update_user_field(u.id, "married_to", target_id)
    await db_update_user_field(target_id, "married_to", u.id)
    await update.message.reply_text("💍 Marriage registered (consent check not implemented).")

async def divorce_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await db_update_user_field(u.id, "married_to", None)
    # also clear other side if any (best effort)
    # find anyone who had married_to = u.id
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET married_to = NULL WHERE married_to = ?", (u.id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("💔 Divorce processed.")

async def friends_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👥 Friend list not implemented in this demo.")

# Rankings
async def top_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    top = await db_get_weekly_top(10)
    if not top:
        await update.message.reply_text("No weekly scores yet.")
        return
    text = "🏆 <b>Weekly leaderboard</b>:\n\n"
    for idx, r in enumerate(top, 1):
        user_display = r.get("username") or str(r.get("user_id"))
        text += f"{idx}. {user_display} — {r.get('score',0)} pts\n"
    await update.message.reply_text(text, parse_mode="HTML")

# Set title (simple placeholder)
async def settitle_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /settitle <title_key>")
        return
    key = ctx.args[0]
    # For demo: accept any key
    await db_update_user_field(update.effective_user.id, "active_title", key)
    await update.message.reply_text(f"Active title set to: {key}")

# -----------------------
# Admin / owner commands
# -----------------------
async def addsudo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Only owner may add sudo.")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /addsudo <user_id>")
        return
    try:
        uid = int(ctx.args[0])
    except:
        await update.message.reply_text("Invalid user id.")
        return
    await db_add_sudo(uid)
    await update.message.reply_text("✅ Added to sudo list.")

async def addcoin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /addcoin <user_id> <amount>")
        return
    try:
        uid = int(ctx.args[0]); amt = int(ctx.args[1])
    except:
        await update.message.reply_text("Invalid args.")
        return
    await db_add_coins(uid, amt)
    await update.message.reply_text(f"✅ Added {amt} coins to {uid}.")

async def sudolist_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return
    rows = await db_list_sudo()
    await update.message.reply_text("Sudo admins:\n" + "\n".join(str(r) for r in rows))

async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(ctx.args)
    # WARNING: naive broadcast - may be slow/limited by API rate limiting
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = [r["user_id"] for r in cur.fetchall()]
    conn.close()
    success = 0
    for uid in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"📢 {msg}")
            success += 1
        except Exception:
            pass
    await update.message.reply_text(f"Broadcast sent to {success}/{len(users)} users.")

async def backup_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    fname = Path(BACKUP_DIR) / f"backup-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.db"
    # copy sqlite file
    try:
        # close any open sqlite connections in this process are ephemeral; use shutil
        import shutil
        shutil.copyfile(DB_FILE, str(fname))
        await update.message.reply_text(f"✅ Backup created: {fname.name}")
    except Exception as e:
        log.exception("Backup failed")
        await update.message.reply_text(f"Backup failed: {e}")

async def restore_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /restore <backup_filename>")
        return
    fname = Path(BACKUP_DIR) / ctx.args[0]
    if not fname.exists():
        await update.message.reply_text("File not found.")
        return
    try:
        import shutil
        shutil.copyfile(str(fname), DB_FILE)
        await update.message.reply_text("✅ Restored backup. Restart the bot to apply.")
    except Exception as e:
        await update.message.reply_text(f"Restore failed: {e}")

async def systemcheck_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_owner(update.effective_user.id):
        await update.message.reply_text("Admin only.")
        return
    # give a simple health summary
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as users FROM users")
    users = cur.fetchone()["users"]
    cur.execute("SELECT COUNT(*) as cards FROM cards")
    cards = cur.fetchone()["cards"]
    conn.close()
    text = f"🤖 System check\n\nUsers: {users}\nCards: {cards}\nDB file: {DB_FILE}\nTime: {datetime.utcnow().isoformat()} UTC"
    await update.message.reply_text(text)

async def allclear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("Owner only.")
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users")
    cur.execute("DELETE FROM inventory")
    cur.execute("DELETE FROM weekly_board")
    conn.commit()
    conn.close()
    await update.message.reply_text("Database cleared (users/inventory/weekly).")

# Media upload handler placeholder
async def handle_upload_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Placeholder: accept media and reply acknowledging upload
    if update.message.photo:
        await update.message.reply_text("Photo received. (Upload handling not implemented in demo.)")
    elif update.message.video:
        await update.message.reply_text("Video received. (Upload handling not implemented in demo.)")
    elif update.message.document:
        await update.message.reply_text("Document received. (Upload handling not implemented in demo.)")
    else:
        await update.message.reply_text("Media received.")

# Error handler
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error("Exception while handling update", exc_info=ctx.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("⚠️ An error occurred. Please try again later.")
    except Exception:
        pass

# Weekly reset job
async def weekly_reset_job(context: ContextTypes.DEFAULT_TYPE):
    """Runs daily. If it's Monday, reward and reset weekly board."""
    today = date.today()
    if today.weekday() != 0:  # 0 = Monday
        return
    log.info("Weekly reset running...")
    top = await db_get_weekly_top(1)
    if top:
        winner = top[0]
        try:
            await db_add_coins(winner["user_id"], 2000)
            await context.bot.send_message(chat_id=winner["user_id"],
                                           text="🏆 You are weekly winner! +2,000 coins awarded!")
        except Exception as e:
            log.error(f"Could not notify weekly winner: {e}")
    await db_reset_weekly_board()
    log.info("Weekly board reset complete.")

# Set Bot commands in menu
async def set_commands(app):
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "🏠 Start the bot"),
            BotCommand("help", "📖 Command list"),
            BotCommand("balance", "💰 View profile & balance"),
            BotCommand("daily", "🎁 Claim daily bonus"),
            BotCommand("shop", "🏪 Item shop"),
            BotCommand("buy", "🛍️ Buy an item"),
            BotCommand("slots", "🎰 Play slots"),
            BotCommand("basket", "🏀 Play basketball"),
            BotCommand("wheel", "🎡 Spin the wheel"),
            BotCommand("catch", "🎴 Catch a card"),
            BotCommand("inventory", "📦 View card collection"),
            BotCommand("set", "⭐ Set favorite card"),
            BotCommand("removeset", "❌ Remove favorite card"),
            BotCommand("givecoin", "💸 Send coins"),
            BotCommand("marry", "💍 Propose marriage"),
            BotCommand("divorce", "💔 Get divorced"),
            BotCommand("friends", "👥 Friend list"),
            BotCommand("top", "🏆 Leaderboard"),
            BotCommand("settitle", "🎭 Set active title"),
        ])
        log.info("Bot commands menu set")
    except Exception as e:
        log.warning("Failed to set bot commands: %s", e)

# Startup tasks
async def on_startup(app):
    log.info("Initializing database...")
    init_db()
    init_defaults()
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    await set_commands(app)
    # notify owner
    try:
        if OWNER_ID:
            await app.bot.send_message(chat_id=OWNER_ID, text=f"✅ Bot started at {datetime.utcnow().isoformat()} UTC")
    except Exception:
        pass
    log.info("Startup complete.")

# Main
def main():
    if not BOT_TOKEN:
        log.critical("BOT_TOKEN not set in environment (.env or env var BOT_TOKEN)")
        sys.exit(1)
    if OWNER_ID == 0:
        log.warning("OWNER_ID not set. Owner-only commands won't be functional.")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("settitle", settitle_cmd))

    app.add_handler(CommandHandler("slots", slots_cmd))
    app.add_handler(CommandHandler("basket", basket_cmd))
    app.add_handler(CommandHandler("wheel", wheel_cmd))

    app.add_handler(CommandHandler("catch", catch_cmd))
    app.add_handler(CommandHandler("set", set_cmd))
    app.add_handler(CommandHandler("removeset", removeset_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))

    app.add_handler(CommandHandler("givecoin", givecoin_cmd))
    app.add_handler(CommandHandler("marry", marry_cmd))
    app.add_handler(CommandHandler("divorce", divorce_cmd))
    app.add_handler(CommandHandler("friends", friends_cmd))

    app.add_handler(CommandHandler("top", top_cmd))

    # Admin / Owner
    app.add_handler(CommandHandler("addsudo", addsudo_cmd))
    app.add_handler(CommandHandler("addcoin", addcoin_cmd))
    app.add_handler(CommandHandler("sudolist", sudolist_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(CommandHandler("systemcheck", systemcheck_cmd))
    app.add_handler(CommandHandler("allclear", allclear_cmd))

    # Media handler
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.ANIMATION, handle_upload_media))

    app.add_error_handler(error_handler)

    # Schedule daily job to run daily (job queue available after start)
    job_queue = app.job_queue
    # run weekly_reset_job daily at 00:00 UTC (handler checks Monday)
    job_queue.run_daily(weekly_reset_job, time=dtime(0, 0, 0))
    log.info("Weekly reset job scheduled (daily check, reward on Monday)")

    log.info("Bot starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

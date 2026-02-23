# ════════════════════════════════════════════
# 👤 User Handlers: /balance /daily /shop /buy
# ════════════════════════════════════════════
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from utils import (
    mention, safe_name, xp_bar, fmt_coins, rarity_stars,
    calc_daily_bonus, is_new_day, today_str, make_bar
)
from config import LEVEL_XP_REQUIREMENTS, RARITY_CONFIG

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# /balance
# ─────────────────────────────────────────────
async def balance_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj  = update.effective_user
    user   = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    await db.ensure_weekly_entry(u_obj.id, u_obj.username or u_obj.first_name)

    level    = user["level"]
    xp       = user["xp"]
    coins    = user["coins"]
    streak   = user["streak"]
    married  = user["married_to"]
    fav_card = await db.get_favorite_card(u_obj.id)
    titles   = await db.get_user_titles(u_obj.id)
    active_t = user.get("active_title", "t1")

    # Find active title
    cur_title = next((t for t in titles if t["title_key"] == active_t), None)
    title_str = f"{cur_title['emoji']} {cur_title['name']}" if cur_title else "🌱 Novice"

    # XP bar
    max_xp = LEVEL_XP_REQUIREMENTS[min(level, len(LEVEL_XP_REQUIREMENTS)-1)]
    xb     = xp_bar(level, xp)

    # Marriage info
    spouse_str = "💔 Single"
    if married:
        spouse = await db.get_user(married)
        if spouse:
            spouse_str = f"💍 {spouse.get('first_name') or spouse.get('username','?')}"

    # Favorite card
    card_str = "🃏 None set"
    if fav_card:
        card_str = f"{rarity_stars(fav_card['rarity'])} {fav_card['name']} [{fav_card['movie']}]"

    # Achievements count
    achs = await db.get_user_achievements(u_obj.id)

    # Rank position
    top = await db.get_top_users(100)
    rank = next((i+1 for i,t in enumerate(top) if t["user_id"]==u_obj.id), "N/A")

    text = (
        f"╔═══════════════════════╗\n"
        f"   💼 <b>PLAYER PROFILE</b>\n"
        f"╚═══════════════════════╝\n\n"
        f"👤 <b>{u_obj.first_name}</b>  {title_str}\n"
        f"🏆 Rank: <b>#{rank}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Coins:</b> {fmt_coins(coins)}\n"
        f"⭐ <b>Level:</b> {level}\n"
        f"📊 XP: {xb}\n"
        f"🔥 <b>Streak:</b> {streak} days\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎴 <b>Fav Card:</b> {card_str}\n"
        f"{spouse_str}\n"
        f"🎖️ Achievements: <b>{len(achs)}/15</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Cards: <b>{user['total_caught']}</b> total caught\n"
        f"🎰 Jackpots: <b>{user['jackpots']}</b>\n"
        f"🏀 Best Combo: <b>{user['best_combo']}</b>\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /daily
# ─────────────────────────────────────────────
async def daily_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    last_daily = user.get("last_daily")

    if not is_new_day(last_daily):
        # Already claimed
        from datetime import datetime, timedelta
        tomorrow = date.today() + timedelta(days=1)
        text = (
            f"⏰ <b>Already Claimed!</b>\n\n"
            f"🔥 Current Streak: <b>{user['streak']} days</b>\n"
            f"🕒 Next daily: <b>{tomorrow.strftime('%Y-%m-%d')}</b>\n\n"
            f"💡 Come back tomorrow for more bonus!"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    # Calculate new streak
    yesterday = (date.today() - __import__("datetime").timedelta(days=1)).isoformat()
    new_streak = (user["streak"] + 1) if (last_daily and last_daily[:10] == yesterday) else 1
    bonus      = calc_daily_bonus(new_streak)

    # Update DB
    await db.update_user(u_obj.id, streak=new_streak, last_daily=today_str(),
                         days_played=user["days_played"] + 1)
    await db.add_coins(u_obj.id, bonus, tx_type="daily", note=f"Daily streak {new_streak}")
    xp_result = await db.add_xp(u_obj.id, 30)

    # Check missions & achievements
    await db.update_mission_progress(u_obj.id, "streak", 1)
    new_achs = await db.check_achievements(u_obj.id)
    new_tits = await db.check_titles(u_obj.id)

    # Streak milestone emoji
    streak_emoji = "🔥" * min(new_streak // 3 + 1, 5)

    text = (
        f"🎁 <b>DAILY BONUS CLAIMED!</b>\n\n"
        f"{streak_emoji} <b>Streak: {new_streak} days</b>\n\n"
        f"╔═══════════════════╗\n"
        f"  💰 +{fmt_coins(bonus)}\n"
        f"  ✨ +30 XP\n"
        f"╚═══════════════════╝\n\n"
    )

    if new_streak < 7:
        text += f"🔑 Keep going! Longer streaks = more coins!\n"
    elif new_streak == 7:
        text += f"🏆 <b>7-day streak!</b> Achievement Unlocked!\n"
    elif new_streak >= 30:
        text += f"👑 <b>Legendary Streak!</b> You're amazing!\n"

    if xp_result["leveled_up"]:
        text += f"\n🎊 <b>LEVEL UP! → Level {xp_result['new_level']}</b> 🎊"

    if new_achs:
        for a in new_achs:
            text += f"\n{a['badge']} <b>Achievement: {a['name']}</b>!"

    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /shop
# ─────────────────────────────────────────────
async def shop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    items = await db.get_shop_items()

    text = (
        f"🏪 <b>CARD GAME SHOP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Your Balance: {fmt_coins(user['coins'])}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛒 <i>Use /buy &lt;number&gt; to purchase</i>\n\n"
    )

    for i, item in enumerate(items, 1):
        can_afford = "✅" if user["coins"] >= item["price"] else "❌"
        text += (
            f"<b>[{i}]</b> {can_afford} <b>{item['name']}</b>\n"
            f"  📝 {item['description']}\n"
            f"  💰 Price: {item['price']:,} coins\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━━━\n💡 <i>Limited-time items refresh daily!</i>"
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /buy <number>
# ─────────────────────────────────────────────
async def buy_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user

    if not ctx.args:
        await update.message.reply_text(
            "❓ Usage: <code>/buy &lt;item_number&gt;</code>\n"
            "Check /shop for item numbers.",
            parse_mode="HTML"
        )
        return

    try:
        item_num = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid item number.")
        return

    items = await db.get_shop_items()
    if item_num < 1 or item_num > len(items):
        await update.message.reply_text(f"❌ Invalid item number. Use 1-{len(items)}.")
        return

    item_key = items[item_num - 1]["item_key"]
    await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    result = await db.buy_item(u_obj.id, item_key)

    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}")
        return

    item = result["item"]
    text = (
        f"🛍️ <b>PURCHASE SUCCESSFUL!</b>\n\n"
        f"✅ <b>{item['name']}</b> acquired!\n"
        f"📝 {item['description']}\n"
        f"💰 Paid: <b>{item['price']:,} coins</b>\n\n"
        f"📦 Check your inventory anytime!"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    # Check achievements
    await db.check_achievements(u_obj.id)

#!/usr/bin/env python3
# 🃏 Card Character Collection Telegram Bot — bot.py (fixed, concise)

import asyncio
import logging
import os
import sys
from datetime import datetime, date, time as dtime

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, Application,
    CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

# Local modules (assumed present)
import database as db
from config import (
    BOT_TOKEN, OWNER_ID, BACKUP_DIR, LOG_LEVEL,
    DEFAULT_SHOP_ITEMS, DAILY_MISSIONS, WEEKLY_MISSIONS,
    ACHIEVEMENTS, TITLES
)

# Handlers (these should be implemented in your handlers package)
from handlers.user_handlers     import balance_cmd, daily_cmd, shop_cmd, buy_cmd
from handlers.game_handlers     import slots_cmd, basket_cmd, wheel_cmd
from handlers.card_handlers     import catch_cmd, set_cmd, removeset_cmd, inventory_cmd
from handlers.social_handlers   import givecoin_cmd, marry_cmd, divorce_cmd, friends_cmd
from handlers.ranking_handlers  import top_cmd, titles_cmd, missions_cmd, achievements_cmd
from handlers.admin_handlers    import (
    upload_cmd, uploadvd_cmd, edit_cmd, delete_cmd, confirmdelete_cmd,
    setdrop_cmd, stats_cmd, backup_cmd, restore_cmd, confirmrestore_cmd
)
from handlers.owner_handlers    import (
    addsudo_cmd, addcoin_cmd, sudolist_cmd,
    broadcast_cmd, allclear_cmd, systemcheck_cmd
)

# Optional media upload handler: import if available, otherwise fallback
try:
    from handlers.media_handlers import handle_upload_media
except Exception:
    async def handle_upload_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_message:
            await update.effective_message.reply_text("📥 Upload received. (No media handler installed)")

# Logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("bot.log", encoding="utf-8")]
)
log = logging.getLogger(__name__)

# START
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await db.get_or_create_user(u.id, u.username or "", u.first_name or "")
    await db.ensure_weekly_entry(u.id, u.username or u.first_name or "")
    text = (
        "╔══════════════════════════╗\n"
        "  🃏 <b>CARD COLLECTION BOT</b>\n"
        "╚══════════════════════════╝\n\n"
        f"Welcome, <b>{u.first_name}</b>! 👋\n\n"
        "🎮 <b>Get Started:</b>\n"
        " /daily — Claim daily bonus\n"
        " /catch — Catch a random card\n"
        " /balance — View your profile\n\n"
        "Use /help for all commands."
    )
    await update.message.reply_text(text, parse_mode="HTML")

# HELP
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    is_admin = await db.is_sudo(update.effective_user.id)
    parts = [
        "╔══════════════════════════╗",
        "  📖 <b>COMMAND LIST</b>",
        "╚══════════════════════════╝\n",
        "👤 <b>Player</b>",
        "/balance — Profile & balance",
        "/daily — Daily bonus",
        "/shop — Shop",
        "/buy <num> — Buy item\n",
        "🎮 <b>Games</b>",
        "/slots <amt> /basket <amt> /wheel <amt>\n",
        "🎴 <b>Cards</b>",
        "/catch [name] /inventory /set <id> /removeset <id>\n",
        "👥 <b>Social</b>",
        "/givecoin <amt> /marry /divorce /friends\n",
        "📊 <b>Progress</b>",
        "/top /titles /missions /achievements\n"
    ]
    if is_admin:
        parts += [
            "\n🛠 <b>Admin</b>",
            "/upload /uploadvd /edit <id> /delete <id>",
            "/setdrop /stats /backup /restore\n"
        ]
    if update.effective_user.id == OWNER_ID:
        parts += [
            "\n👑 <b>Owner</b>",
            "/addsudo /addcoin /sudolist /broadcast /allclear /systemcheck\n"
        ]
    await update.message.reply_text("\n".join(parts), parse_mode="HTML")

# Set title
async def settitle_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not ctx.args:
        await update.message.reply_text("❓ Usage: <code>/settitle <title_id></code>", parse_mode="HTML")
        return
    title_key = ctx.args[0]
    my_titles = await db.get_user_titles(u.id)
    earned = {t["title_key"] for t in my_titles}
    if title_key not in earned:
        await update.message.reply_text(f"❌ You haven't earned title <code>{title_key}</code> yet!", parse_mode="HTML")
        return
    await db.update_user(u.id, active_title=title_key)
    t = next((t for t in my_titles if t["title_key"] == title_key), None)
    if t:
        await update.message.reply_text(f"✅ Active title set to: <b>{t['emoji']} {t['name']}</b>", parse_mode="HTML")

# Weekly reset job (runs Mondays)
async def weekly_reset_job(context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    if today.weekday() != 0:  # Monday
        return
    log.info("⚡ Weekly reset running...")
    top = await db.get_weekly_top(1)
    if top:
        winner = top[0]
        await db.add_coins(winner["user_id"], 2000, tx_type="weekly_winner", note="Weekly leaderboard winner!")
        log.info(f"🏆 Weekly winner: {winner.get('username','?')} | +2000 coins")
        try:
            await context.bot.send_message(
                chat_id=winner["user_id"],
                text=("🏆 <b>WEEKLY WINNER!</b>\n\nYou topped the weekly leaderboard!\n🎁 Reward: <b>+2,000 coins</b>"),
                parse_mode="HTML"
            )
        except Exception as e:
            log.error(f"Could not notify winner: {e}")
    await db.reset_weekly_board()
    log.info("✅ Weekly board reset complete")

# Error handler
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error(f"Exception while handling update: {ctx.error}", exc_info=ctx.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ An error occurred. Please try again later.")
        except Exception:
            pass

# Bot command menu
async def set_commands(app: Application):
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
        BotCommand("titles", "🎖️ Your titles"),
        BotCommand("missions", "📋 Daily & weekly missions"),
        BotCommand("achievements", "🏅 Achievement badges"),
        BotCommand("settitle", "🎭 Set active title"),
    ])
    log.info("✅ Bot commands menu set")

# Startup
async def on_startup(app: Application):
    log.info("🚀 Initializing database...")
    await db.init_db()
    await db.init_shop(DEFAULT_SHOP_ITEMS)
    await db.init_missions(DAILY_MISSIONS, WEEKLY_MISSIONS)
    await db.init_achievements(ACHIEVEMENTS)
    await db.init_titles(TITLES)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    await set_commands(app)
    try:
        await app.bot.send_message(
            chat_id=OWNER_ID,
            text=(f"✅ <b>Bot Started!</b>\n\n🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\nUse /systemcheck for full status."),
            parse_mode="HTML"
        )
    except Exception:
        pass
    log.info("✅ Bot startup complete!")

# MAIN
def main():
    if not BOT_TOKEN:
        log.critical("❌ BOT_TOKEN not set in .env!")
        sys.exit(1)
    if OWNER_ID == 0:
        log.warning("⚠️ OWNER_ID not set. Owner commands won't work.")
    log.info("🃏 Starting Card Collection Bot...")

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    # User
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("settitle", settitle_cmd))

    # Games
    app.add_handler(CommandHandler("slots", slots_cmd))
    app.add_handler(CommandHandler("basket", basket_cmd))
    app.add_handler(CommandHandler("wheel", wheel_cmd))

    # Cards
    app.add_handler(CommandHandler("catch", catch_cmd))
    app.add_handler(CommandHandler("set", set_cmd))
    app.add_handler(CommandHandler("removeset", removeset_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))

    # Social
    app.add_handler(CommandHandler("givecoin", givecoin_cmd))
    app.add_handler(CommandHandler("marry", marry_cmd))
    app.add_handler(CommandHandler("divorce", divorce_cmd))
    app.add_handler(CommandHandler("friends", friends_cmd))

    # Rankings
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("titles", titles_cmd))
    app.add_handler(CommandHandler("missions", missions_cmd))
    app.add_handler(CommandHandler("achievements", achievements_cmd))

    # Admin
    app.add_handler(CommandHandler("upload", upload_cmd))
    app.add_handler(CommandHandler("uploadvd", uploadvd_cmd))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("confirmdelete", confirmdelete_cmd))
    app.add_handler(CommandHandler("setdrop", setdrop_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(CommandHandler("confirmrestore", confirmrestore_cmd))

    # Owner
    app.add_handler(CommandHandler("addsudo", addsudo_cmd))
    app.add_handler(CommandHandler("addcoin", addcoin_cmd))
    app.add_handler(CommandHandler("sudolist", sudolist_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("allclear", allclear_cmd))
    app.add_handler(CommandHandler("systemcheck", systemcheck_cmd))

    # Media uploads
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.ANIMATION, handle_upload_media))

    # Error handler
    app.add_error_handler(error_handler)

    # Scheduled job: weekly reset (runs daily check at 00:00 UTC)
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_daily(weekly_reset_job, time=dtime(0, 0))
        log.info("✅ Weekly reset job scheduled")

    log.info("🤖 Bot is running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()

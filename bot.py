#!/usr/bin/env python3
# ╔══════════════════════════════════════════════╗
# ║   🃏 Card Character Collection Telegram Bot  ║
# ║   Version: 2.0  |  python-telegram-bot 20.x  ║
# ╚══════════════════════════════════════════════╝

import asyncio
import logging
import os
import sys
from datetime import datetime, date, timedelta

from telegram import Update, BotCommand
from telegram.ext import (
    Application, ApplicationBuilder,
    CommandHandler, MessageHandler,
    CallbackQueryHandler,
    filters, ContextTypes
)

# ── Local imports ─────────────────────────────
import database as db
from config import (
    BOT_TOKEN, OWNER_ID, BACKUP_DIR, LOG_LEVEL,
    DEFAULT_SHOP_ITEMS, DAILY_MISSIONS, WEEKLY_MISSIONS,
    ACHIEVEMENTS, TITLES
)

# Handlers
from handlers.user_handlers    import balance_cmd, daily_cmd, shop_cmd, buy_cmd
from handlers.game_handlers    import slots_cmd, basket_cmd, wheel_cmd
# bot.py ထဲက Import ကို ဒီလို ပြင်ပါ
from handlers.card_handlers    import (
    catch_cmd,
    set_cmd,
    removeset_cmd,
    inventory_cmd
)

from handlers.social_handlers  import givecoin_cmd, marry_cmd, divorce_cmd, friends_cmd
from handlers.ranking_handlers import top_cmd, titles_cmd, missions_cmd, achievements_cmd
from handlers.admin_handlers   import (
    upload_cmd, uploadvd_cmd, edit_cmd, delete_cmd, confirmdelete_cmd,
    setdrop_cmd, stats_cmd, bac kup_cmd, restore_cmd, confirmrestore_cmd
)
from handlers.owner_handlers   import (
    addsudo_cmd, addcoin_cmd, sudolist_cmd,
    broadcast_cmd, allclear_cmd, systemcheck_cmd
)

# ── Logging setup ─────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# START / HELP
# ─────────────────────────────────────────────
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = await db.get_or_create_user(u.id, u.username or "", u.first_name or "")
    await db.ensure_weekly_entry(u.id, u.username or u.first_name or "")

    text = (
        f"╔══════════════════════════╗\n"
        f"   🃏 <b>CARD COLLECTION BOT</b>\n"
        f"╚══════════════════════════╝\n\n"
        f"Welcome, <b>{u.first_name}</b>! 👋\n\n"
        f"🎮 <b>Get Started:</b>\n"
        f"  /daily  — Claim daily bonus\n"
        f"  /catch  — Catch a random card\n"
        f"  /balance — View your profile\n\n"
        f"🃏 <b>Cards:</b>\n"
        f"  /catch &lt;name&gt; · /inventory · /set &lt;id&gt;\n\n"
        f"🎮 <b>Games:</b>\n"
        f"  /slots · /basket · /wheel\n\n"
        f"📊 <b>Progress:</b>\n"
        f"  /missions · /achievements · /top\n\n"
        f"💡 Use /help for all commands!"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    is_admin = await db.is_sudo(update.effective_user.id)

    text = (
        "╔══════════════════════════╗\n"
        "   📖 <b>COMMAND LIST</b>\n"
        "╚══════════════════════════╝\n\n"

        "👤 <b>Player</b>\n"
        "/balance — Profile & stats\n"
        "/daily — Daily bonus\n"
        "/shop — Item shop\n"
        "/buy &lt;num&gt; — Buy item\n\n"

        "🎮 <b>Games</b>\n"
        "/slots &lt;amount&gt; — Slot machine\n"
        "/basket &lt;amount&gt; — Basketball\n"
        "/wheel &lt;amount&gt; — Wheel of fortune\n\n"

        "🎴 <b>Cards</b>\n"
        "/catch [name] — Catch a card\n"
        "/inventory — View collection\n"
        "/set &lt;id&gt; — Set favorite card\n"
        "/removeset &lt;id&gt; — Remove favorite\n\n"

        "👥 <b>Social</b>\n"
        "/givecoin &lt;amt&gt; — Transfer coins\n"
        "/marry — Propose (reply)\n"
        "/divorce — End marriage\n"
        "/friends — Friend list\n\n"

        "📊 <b>Rankings</b>\n"
        "/top — Leaderboard\n"
        "/titles — Your titles\n"
        "/missions — Daily/weekly missions\n"
        "/achievements — Achievement badges\n"
    )

    if is_admin:
        text += (
            "\n🛠 <b>Admin</b>\n"
            "/upload — Upload image card\n"
            "/uploadvd — Upload video card\n"
            "/edit &lt;id&gt; &lt;name&gt;|&lt;movie&gt; — Edit card\n"
            "/delete &lt;id&gt; — Delete card\n"
            "/setdrop &lt;rate&gt; — Set drop rate\n"
            "/stats — Server statistics\n"
            "/backup — Create DB backup\n"
            "/restore — Restore from backup\n"
        )

    if update.effective_user.id == OWNER_ID:
        text += (
            "\n👑 <b>Owner</b>\n"
            "/addsudo — Add sudo admin\n"
            "/addcoin &lt;id&gt; &lt;amt&gt; — Give coins\n"
            "/sudolist — View admins\n"
            "/broadcast &lt;msg&gt; — Message all\n"
            "/allclear — Reset database\n"
            "/systemcheck — Bot health\n"
        )

    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# SETTITLE command
# ─────────────────────────────────────────────
async def settitle_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    if not ctx.args:
        await update.message.reply_text("❓ Usage: <code>/settitle &lt;title_id&gt;</code>", parse_mode="HTML")
        return

    title_key = ctx.args[0]
    my_titles = await db.get_user_titles(u_obj.id)
    earned    = {t["title_key"] for t in my_titles}

    if title_key not in earned:
        await update.message.reply_text(f"❌ You haven't earned title <code>{title_key}</code> yet!", parse_mode="HTML")
        return

    await db.update_user(u_obj.id, active_title=title_key)
    title_data = next((t for t in my_titles if t["title_key"] == title_key), None)
    if title_data:
        await update.message.reply_text(
            f"✅ Active title set to: <b>{title_data['emoji']} {title_data['name']}</b>",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────
# WEEKLY RESET JOB
# ─────────────────────────────────────────────
async def weekly_reset_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Runs every Monday to reset weekly leaderboard and reward top player."""
    today = date.today()
    if today.weekday() != 0:   # 0 = Monday
        return

    log.info("⚡ Weekly reset running...")
    top = await db.get_weekly_top(1)
    if top:
        winner = top[0]
        await db.add_coins(winner["user_id"], 2000, tx_type="weekly_winner",
                          note="Weekly leaderboard winner!")
        log.info(f"🏆 Weekly winner: {winner.get('username','?')} | +2000 coins")
        try:
            await ctx.bot.send_message(
                chat_id=winner["user_id"],
                text=(
                    "🏆 <b>WEEKLY WINNER!</b>\n\n"
                    "You topped the weekly leaderboard!\n"
                    "🎁 Reward: <b>+2,000 coins</b> added!\n\n"
                    "Keep it up! 🔥"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            log.error(f"Could not notify winner: {e}")

    await db.reset_weekly_board()
    log.info("✅ Weekly board reset complete")


# ─────────────────────────────────────────────
# ERROR HANDLER
# ─────────────────────────────────────────────
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error(f"Exception while handling update: {ctx.error}", exc_info=ctx.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again later."
            )
        except Exception:
            pass


# ─────────────────────────────────────────────
# BOT COMMAND MENU
# ─────────────────────────────────────────────
async def set_commands(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start",        "🏠 Start the bot"),
        BotCommand("help",         "📖 Command list"),
        BotCommand("balance",      "💰 View profile & balance"),
        BotCommand("daily",        "🎁 Claim daily bonus"),
        BotCommand("shop",         "🏪 Item shop"),
        BotCommand("buy",          "🛍️ Buy an item"),
        BotCommand("slots",        "🎰 Play slots"),
        BotCommand("basket",       "🏀 Play basketball"),
        BotCommand("wheel",        "🎡 Spin the wheel"),
        BotCommand("catch",        "🎴 Catch a card"),
        BotCommand("inventory",    "📦 View card collection"),
        BotCommand("set",          "⭐ Set favorite card"),
        BotCommand("removeset",    "❌ Remove favorite card"),
        BotCommand("givecoin",     "💸 Send coins"),
        BotCommand("marry",        "💍 Propose marriage"),
        BotCommand("divorce",      "💔 Get divorced"),
        BotCommand("friends",      "👥 Friend list"),
        BotCommand("top",          "🏆 Leaderboard"),
        BotCommand("titles",       "🎖️ Your titles"),
        BotCommand("missions",     "📋 Daily & weekly missions"),
        BotCommand("achievements", "🏅 Achievement badges"),
        BotCommand("settitle",     "🎭 Set active title"),
    ])
    log.info("✅ Bot commands menu set")


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
async def on_startup(app: Application):
    log.info("🚀 Initializing database...")
    await db.init_db()
    await db.init_shop(DEFAULT_SHOP_ITEMS)
    await db.init_missions(DAILY_MISSIONS, WEEKLY_MISSIONS)
    await db.init_achievements(ACHIEVEMENTS)
    await db.init_titles(TITLES)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    await set_commands(app)

    # Notify owner
    try:
        await app.bot.send_message(
            chat_id=OWNER_ID,
            text=(
                "✅ <b>Bot Started!</b>\n\n"
                f"🕒 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                "Use /systemcheck for full status."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    log.info("✅ Bot startup complete!")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        log.critical("❌ BOT_TOKEN not set in .env!")
        sys.exit(1)

    if OWNER_ID == 0:
        log.warning("⚠️  OWNER_ID not set. Owner commands won't work.")

    log.info("🃏 Starting Card Collection Bot...")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .build()
    )

    # ── User Commands ──────────────────────────
    app.add_handler(CommandHandler("start",        start_cmd))
    app.add_handler(CommandHandler("help",         help_cmd))
    app.add_handler(CommandHandler("balance",      balance_cmd))
    app.add_handler(CommandHandler("daily",        daily_cmd))
    app.add_handler(CommandHandler("shop",         shop_cmd))
    app.add_handler(CommandHandler("buy",          buy_cmd))
    app.add_handler(CommandHandler("settitle",     settitle_cmd))

    # ── Game Commands ──────────────────────────
    app.add_handler(CommandHandler("slots",        slots_cmd))
    app.add_handler(CommandHandler("basket",       basket_cmd))
    app.add_handler(CommandHandler("wheel",        wheel_cmd))

    # ── Card Commands ──────────────────────────
    app.add_handler(CommandHandler("catch",        catch_cmd))
    app.add_handler(CommandHandler("set",          set_cmd))
    app.add_handler(CommandHandler("removeset",    removeset_cmd))
    app.add_handler(CommandHandler("inventory",    inventory_cmd))

    # ── Social Commands ────────────────────────
    app.add_handler(CommandHandler("givecoin",     givecoin_cmd))
    app.add_handler(CommandHandler("marry",        marry_cmd))
    app.add_handler(CommandHandler("divorce",      divorce_cmd))
    app.add_handler(CommandHandler("friends",      friends_cmd))

    # ── Ranking Commands ───────────────────────
    app.add_handler(CommandHandler("top",          top_cmd))
    app.add_handler(CommandHandler("titles",       titles_cmd))
    app.add_handler(CommandHandler("missions",     missions_cmd))
    app.add_handler(CommandHandler("achievements", achievements_cmd))

    # ── Admin Commands ─────────────────────────
    app.add_handler(CommandHandler("upload",         upload_cmd))
    app.add_handler(CommandHandler("uploadvd",       uploadvd_cmd))
    app.add_handler(CommandHandler("edit",           edit_cmd))
    app.add_handler(CommandHandler("delete",         delete_cmd))
    app.add_handler(CommandHandler("confirmdelete",  confirmdelete_cmd))
    app.add_handler(CommandHandler("setdrop",        setdrop_cmd))
    app.add_handler(CommandHandler("stats",          stats_cmd))
    app.add_handler(CommandHandler("backup",         backup_cmd))
    app.add_handler(CommandHandler("restore",        restore_cmd))
    app.add_handler(CommandHandler("confirmrestore", confirmrestore_cmd))

    # ── Owner Commands ─────────────────────────
    app.add_handler(CommandHandler("addsudo",      addsudo_cmd))
    app.add_handler(CommandHandler("addcoin",      addcoin_cmd))
    app.add_handler(CommandHandler("sudolist",     sudolist_cmd))
    app.add_handler(CommandHandler("broadcast",    broadcast_cmd))
    app.add_handler(CommandHandler("allclear",     allclear_cmd))
    app.add_handler(CommandHandler("systemcheck",  systemcheck_cmd))

    # ── Media upload handler ────────────────────
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.ANIMATION,
        handle_upload_media
    ))

    # ── Error handler ──────────────────────────
    app.add_error_handler(error_handler)

    # ── Scheduled Jobs ─────────────────────────
    job_queue = app.job_queue
    if job_queue:
        # Weekly reset - check every 24 hours at midnight UTC
        job_queue.run_daily(weekly_reset_job, time=__import__("datetime").time(0, 0, 0))
        log.info("✅ Weekly reset job scheduled")

    log.info("🤖 Bot is running! Press Ctrl+C to stop.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()

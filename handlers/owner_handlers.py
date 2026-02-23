# ════════════════════════════════════════════
# 👑 Owner Handlers: /addsudo /addcoin /sudolist /broadcast /allclear /systemcheck
# ════════════════════════════════════════════
import logging
import os
import platform
import sys
import time
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import OWNER_ID, DB_PATH, BACKUP_DIR
from utils import fmt_coins

log = logging.getLogger(__name__)

# Pending confirmations
_allclear_stage: dict = {}   # user_id -> stage (1 or 2)


def owner_only(func):
    """Decorator that blocks non-owners."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("🚫 Owner-only command.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


# ─────────────────────────────────────────────
# /addsudo (Reply to user)
# ─────────────────────────────────────────────
@owner_only
async def addsudo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user

    target = None
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    elif ctx.args:
        try:
            uid    = int(ctx.args[0])
            target_user = await db.get_user(uid)
            if target_user:
                # Create a minimal user-like dict
                class FakeUser:
                    id         = uid
                    username   = target_user.get("username", "")
                    first_name = target_user.get("first_name", "")
                    is_bot     = False
                target = FakeUser()
        except ValueError:
            pass

    if not target:
        await update.message.reply_text(
            "❓ Reply to a user or provide user ID:\n<code>/addsudo &lt;user_id&gt;</code>",
            parse_mode="HTML"
        )
        return

    if target.is_bot:
        await update.message.reply_text("❌ Can't add a bot as admin.")
        return

    if target.id == OWNER_ID:
        await update.message.reply_text("👑 That's already the Owner!")
        return

    await db.add_sudo(target.id, target.username or "", u_obj.id)
    await db.audit(u_obj.id, "add_sudo", str(target.id), target.username or "")

    await update.message.reply_text(
        f"✅ <b>Sudo Admin Added!</b>\n\n"
        f"👤 {target.first_name or target.username or target.id}\n"
        f"🆔 ID: <code>{target.id}</code>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /addcoin <amount> (Reply OR /addcoin <id> <amount>)
# ─────────────────────────────────────────────
@owner_only
async def addcoin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj  = update.effective_user
    target = None
    amount = 0

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        try:
            amount = int(ctx.args[0]) if ctx.args else 0
        except (ValueError, IndexError):
            amount = 0
    elif ctx.args and len(ctx.args) >= 2:
        try:
            uid    = int(ctx.args[0])
            amount = int(ctx.args[1])
            t_user = await db.get_user(uid)
            if t_user:
                class FU:
                    id         = uid
                    username   = t_user.get("username","")
                    first_name = t_user.get("first_name","")
                target = FU()
        except ValueError:
            pass

    if not target:
        await update.message.reply_text(
            "❓ Usage:\n"
            "Reply + <code>/addcoin &lt;amount&gt;</code>\n"
            "Or: <code>/addcoin &lt;user_id&gt; &lt;amount&gt;</code>",
            parse_mode="HTML"
        )
        return

    if amount == 0:
        await update.message.reply_text("❌ Specify a valid amount.")
        return

    await db.get_or_create_user(target.id, getattr(target, "username", ""), getattr(target, "first_name", ""))
    await db.add_coins(target.id, amount, tx_type="admin_add",
                      from_user=u_obj.id, note="Admin gift")
    await db.audit(u_obj.id, "add_coin", str(target.id), f"{amount} coins")

    fname = getattr(target, "first_name", None) or getattr(target, "username", None) or str(target.id)
    sign  = "+" if amount >= 0 else ""
    await update.message.reply_text(
        f"✅ <b>Coins Added!</b>\n\n"
        f"👤 User: <b>{fname}</b>\n"
        f"💰 Amount: <b>{sign}{fmt_coins(amount)}</b>\n"
        f"📝 Transaction logged!",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /sudolist
# ─────────────────────────────────────────────
@owner_only
async def sudolist_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    sudos = await db.get_sudo_list()

    text = "👮 <b>SUDO ADMIN LIST</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"👑 Owner: <code>{OWNER_ID}</code>\n\n"

    if not sudos:
        text += "No sudo admins yet."
    else:
        for i, s in enumerate(sudos, 1):
            uname = s.get("username") or "N/A"
            added = s.get("added_at", "?")[:10]
            text += f"{i}. <code>{s['user_id']}</code> @{uname}  <i>({added})</i>\n"

    text += f"\n━━━━━━━━━━━━━━━━━━━━━\nTotal sudos: <b>{len(sudos)}</b>"
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /broadcast <message>
# ─────────────────────────────────────────────
@owner_only
async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "📢 Usage: <code>/broadcast &lt;message&gt;</code>\n"
            "Add --pin to pin the message.",
            parse_mode="HTML"
        )
        return

    text_parts = ctx.args[:]
    pin_msg    = "--pin" in text_parts
    if pin_msg:
        text_parts.remove("--pin")

    message = " ".join(text_parts)
    users   = await db.get_all_users()

    sent = failed = 0
    status_msg = await update.message.reply_text(
        f"📡 Broadcasting to {len(users)} users..."
    )

    for u in users:
        try:
            sent_msg = await ctx.bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>BROADCAST</b>\n\n{message}",
                parse_mode="HTML"
            )
            sent += 1
            if pin_msg:
                try:
                    await ctx.bot.pin_chat_message(u["user_id"], sent_msg.message_id)
                except Exception:
                    pass
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"📢 <b>Broadcast Complete!</b>\n\n"
        f"✅ Sent:   {sent}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Total:  {len(users)}",
        parse_mode="HTML"
    )
    await db.audit(update.effective_user.id, "broadcast", "all", message[:100])


# ─────────────────────────────────────────────
# /allclear  (double confirmation)
# ─────────────────────────────────────────────
@owner_only
async def allclear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_id  = update.effective_user.id
    stage = _allclear_stage.get(u_id, 0)

    if stage == 0:
        _allclear_stage[u_id] = 1
        await update.message.reply_text(
            "⚠️ <b>DATABASE RESET WARNING</b>\n\n"
            "This will DELETE all player data:\n"
            "• All users, coins, levels\n"
            "• All cards, inventory\n"
            "• All missions, achievements\n\n"
            "❗ Type <code>/allclear</code> again to proceed to step 2.",
            parse_mode="HTML"
        )
    elif stage == 1:
        _allclear_stage[u_id] = 2
        await update.message.reply_text(
            "🔴 <b>FINAL WARNING!</b>\n\n"
            "All player data will be permanently erased!\n\n"
            "Type <code>/allclear</code> ONE MORE TIME to confirm.\n"
            "This is IRREVERSIBLE.",
            parse_mode="HTML"
        )
    elif stage == 2:
        _allclear_stage.pop(u_id, None)
        await db.clear_all_users()
        await db.audit(u_id, "allclear", "database", "Full wipe")
        await update.message.reply_text(
            "🗑️ <b>DATABASE CLEARED!</b>\n\n"
            "All player data has been erased.\n"
            "Cards and settings remain.",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────
# /systemcheck
# ─────────────────────────────────────────────
@owner_only
async def systemcheck_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import os
    import sys
    import platform

    start = time.time()

    # DB check
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    stats   = await db.get_server_stats()

    # Backup count
    bak_count = 0
    if os.path.isdir(BACKUP_DIR):
        bak_count = len([f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")])

    elapsed = (time.time() - start) * 1000

    # Python / OS info
    py_ver  = sys.version.split()[0]
    os_name = platform.system()
    now     = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        f"🖥️ <b>SYSTEM CHECK</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 Bot Status:   <b>✅ Online</b>\n"
        f"🗄️  DB Status:    <b>✅ Connected</b>\n"
        f"💾 DB Size:      <b>{db_size/1024:.1f} KB</b>\n"
        f"📦 Backups:      <b>{bak_count}</b> files\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users:        <b>{stats['total_users']:,}</b>\n"
        f"🃏 Cards:        <b>{stats['total_cards']:,}</b>\n"
        f"💰 Total Coins:  <b>{stats['total_coins']:,}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🐍 Python:       <b>{py_ver}</b>\n"
        f"💻 OS:           <b>{os_name}</b>\n"
        f"⚡ Response:     <b>{elapsed:.1f}ms</b>\n"
        f"🕒 UTC Time:     <code>{now}</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

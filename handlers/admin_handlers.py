# ════════════════════════════════════════════
# 🛠 Admin Handlers: /upload /uploadvd /edit /delete /setdrop /stats /backup /restore
# ════════════════════════════════════════════
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from config import DB_PATH, BACKUP_DIR

log = logging.getLogger(__name__)

RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

# ── Pending uploads waiting for photo/video ──
_pending_uploads: dict = {}   # user_id -> {name, movie, rarity, type}


# ─────────────────────────────────────────────
# /upload
# ─────────────────────────────────────────────
async def upload_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if len(ctx.args) < 3:
        await update.message.reply_text(
            "📤 <b>Card Upload</b>\n\n"
            "Usage:\n"
            "<code>/upload &lt;name&gt; | &lt;movie&gt; | &lt;rarity&gt;</code>\n\n"
            "Then send the card <b>photo</b> as a reply.\n\n"
            f"Rarities: {', '.join(RARITIES)}",
            parse_mode="HTML"
        )
        return

    text = " ".join(ctx.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ Format: <code>Name | Movie | Rarity</code>", parse_mode="HTML")
        return

    name, movie, rarity = parts[0], parts[1], parts[2]
    if rarity not in RARITIES:
        await update.message.reply_text(f"❌ Invalid rarity! Choose: {', '.join(RARITIES)}")
        return

    _pending_uploads[u_obj.id] = {"name": name, "movie": movie, "rarity": rarity, "type": "photo"}
    await update.message.reply_text(
        f"✅ Card info saved:\n"
        f"🃏 Name:   <b>{name}</b>\n"
        f"🎬 Movie:  <b>{movie}</b>\n"
        f"⭐ Rarity: <b>{rarity}</b>\n\n"
        f"📸 Now send the card <b>photo</b>!",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /uploadvd (video card)
# ─────────────────────────────────────────────
async def uploadvd_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if len(ctx.args) < 3:
        await update.message.reply_text(
            "🎥 <b>Video Card Upload</b>\n\n"
            "Usage: <code>/uploadvd &lt;name&gt; | &lt;movie&gt; | &lt;rarity&gt;</code>\n"
            "Then send the <b>video/gif</b>.",
            parse_mode="HTML"
        )
        return

    text  = " ".join(ctx.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ Format: <code>Name | Movie | Rarity</code>", parse_mode="HTML")
        return

    name, movie, rarity = parts[0], parts[1], parts[2]
    if rarity not in RARITIES:
        await update.message.reply_text(f"❌ Invalid rarity! Choose: {', '.join(RARITIES)}")
        return

    _pending_uploads[u_obj.id] = {"name": name, "movie": movie, "rarity": rarity, "type": "video"}
    await update.message.reply_text(
        f"✅ Video card info saved:\n"
        f"🃏 <b>{name}</b> | 🎬 {movie} | ⭐ {rarity}\n\n"
        f"🎥 Now send the <b>video/GIF</b>!",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# Handle photo/video after /upload or /uploadvd
# ─────────────────────────────────────────────
async def handle_upload_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if u_obj.id not in _pending_uploads:
        return

    pending = _pending_uploads.pop(u_obj.id)
    file_id   = None
    file_type = pending["type"]

    if file_type == "photo" and update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif file_type == "video" and update.message.video:
        file_id = update.message.video.file_id
    elif file_type == "video" and update.message.animation:
        file_id = update.message.animation.file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text(
            f"❌ Please send a {'photo' if file_type=='photo' else 'video/GIF'}."
        )
        return

    card_id = await db.add_card(
        pending["name"], pending["movie"], pending["rarity"],
        file_id, file_type, u_obj.id
    )
    await db.audit(u_obj.id, "upload_card", f"card#{card_id}", pending["name"])

    await update.message.reply_text(
        f"✅ <b>Card Uploaded!</b>\n\n"
        f"🆔 Card ID: <b>{card_id}</b>\n"
        f"🃏 Name:    <b>{pending['name']}</b>\n"
        f"🎬 Movie:   <b>{pending['movie']}</b>\n"
        f"⭐ Rarity:  <b>{pending['rarity']}</b>\n"
        f"📁 Type:    {file_type}",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /edit <id> <name> | <movie>
# ─────────────────────────────────────────────
async def edit_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if len(ctx.args) < 2:
        await update.message.reply_text(
            "✏️ Usage: <code>/edit &lt;id&gt; &lt;new_name&gt; | &lt;new_movie&gt;</code>",
            parse_mode="HTML"
        )
        return

    try:
        card_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid card ID.")
        return

    rest  = " ".join(ctx.args[1:])
    parts = [p.strip() for p in rest.split("|")]
    new_name  = parts[0] if len(parts) > 0 else None
    new_movie = parts[1] if len(parts) > 1 else None

    card = await db.get_card(card_id)
    if not card:
        await update.message.reply_text(f"❌ Card #{card_id} not found.")
        return

    final_name  = new_name  or card["name"]
    final_movie = new_movie or card["movie"]

    await db.edit_card(card_id, final_name, final_movie)
    await db.audit(u_obj.id, "edit_card", f"card#{card_id}", f"{card['name']} → {final_name}")

    await update.message.reply_text(
        f"✅ <b>Card #{card_id} Updated!</b>\n\n"
        f"🃏 Name:  {card['name']} → <b>{final_name}</b>\n"
        f"🎬 Movie: {card['movie']} → <b>{final_movie}</b>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /delete <id>
# ─────────────────────────────────────────────
_pending_delete: dict = {}  # user_id -> card_id

async def delete_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if not ctx.args:
        await update.message.reply_text("❓ Usage: <code>/delete &lt;card_id&gt;</code>", parse_mode="HTML")
        return

    try:
        card_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid card ID.")
        return

    card = await db.get_card(card_id)
    if not card:
        await update.message.reply_text(f"❌ Card #{card_id} not found.")
        return

    _pending_delete[u_obj.id] = card_id

    await update.message.reply_text(
        f"⚠️ <b>Confirm Delete?</b>\n\n"
        f"🃏 <b>#{card_id}</b> — {card['name']}\n"
        f"🎬 {card['movie']}  |  ⭐ {card['rarity']}\n\n"
        f"Reply <code>/confirmdelete</code> to confirm.\n"
        f"This will remove the card from ALL players!",
        parse_mode="HTML"
    )


async def confirmdelete_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if u_obj.id not in _pending_delete:
        await update.message.reply_text("❌ No pending delete. Use /delete first.")
        return

    card_id = _pending_delete.pop(u_obj.id)
    card    = await db.get_card(card_id)
    await db.delete_card(card_id)
    await db.audit(u_obj.id, "delete_card", f"card#{card_id}", card["name"] if card else "?")

    await update.message.reply_text(f"🗑️ Card <b>#{card_id}</b> deleted from database.", parse_mode="HTML")


# ─────────────────────────────────────────────
# /setdrop <rate>
# ─────────────────────────────────────────────
async def setdrop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if not ctx.args:
        current = await db.get_drop_rate()
        await update.message.reply_text(
            f"⚙️ Current drop rate: <b>{current}x</b>\n"
            f"Usage: <code>/setdrop &lt;multiplier&gt;</code>\n"
            f"Example: <code>/setdrop 2.0</code> for double drop rate",
            parse_mode="HTML"
        )
        return

    try:
        rate = float(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid rate. Use a number like 1.5 or 2.0")
        return

    if rate < 0.1 or rate > 10.0:
        await update.message.reply_text("❌ Rate must be between 0.1 and 10.0")
        return

    old_rate = await db.get_drop_rate()
    await db.set_drop_rate(rate, u_obj.id)
    await db.audit(u_obj.id, "set_drop", "global", f"{old_rate} → {rate}")

    await update.message.reply_text(
        f"✅ <b>Drop Rate Updated!</b>\n\n"
        f"Old: {old_rate}x\n"
        f"New: <b>{rate}x</b>\n\n"
        f"All catch rates now multiplied by {rate}x!",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# /stats
# ─────────────────────────────────────────────
async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    stats      = await db.get_server_stats()
    drop_rate  = await db.get_drop_rate()
    total_cards = await db.count_cards()

    text = (
        f"📊 <b>SERVER STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total Players:     <b>{stats['total_users']:,}</b>\n"
        f"🃏 Total Cards:       <b>{stats['total_cards']:,}</b>\n"
        f"📦 Cards Caught:      <b>{stats['total_caught']:,}</b>\n"
        f"💰 Total Coins:       <b>{stats['total_coins']:,}</b>\n"
        f"💸 Transactions:      <b>{stats['total_txs']:,}</b>\n"
        f"👮 Sudo Admins:       <b>{stats['total_sudos']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️  Drop Rate:         <b>{drop_rate}x</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Report time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /backup
# ─────────────────────────────────────────────
async def backup_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{ts}.db"
    dst      = os.path.join(BACKUP_DIR, filename)

    try:
        shutil.copy2(DB_PATH, dst)
        size = os.path.getsize(dst)

        # Log backup
        async with __import__("aiosqlite").connect(DB_PATH) as dbc:
            await dbc.execute(
                "INSERT INTO backups (filename, size_bytes) VALUES (?,?)",
                (filename, size)
            )
            await dbc.commit()

        await db.audit(u_obj.id, "backup", filename, f"size={size}")

        # Send as document
        with open(dst, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption=(
                    f"✅ <b>Backup Created!</b>\n\n"
                    f"📁 File: <code>{filename}</code>\n"
                    f"💾 Size: {size/1024:.1f} KB\n"
                    f"🕒 Time: {ts}"
                ),
                parse_mode="HTML"
            )
    except Exception as e:
        log.error(f"Backup error: {e}")
        await update.message.reply_text(f"❌ Backup failed: {e}")


# ─────────────────────────────────────────────
# /restore (reply to backup file)
# ─────────────────────────────────────────────
_pending_restore: dict = {}

async def restore_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text(
            "📥 <b>Restore Database</b>\n\n"
            "Reply to a <b>.db backup file</b> with /restore.\n"
            "⚠️ This will overwrite the current database!",
            parse_mode="HTML"
        )
        return

    doc = update.message.reply_to_message.document
    if not doc.file_name.endswith(".db"):
        await update.message.reply_text("❌ File must be a .db backup file.")
        return

    _pending_restore[u_obj.id] = doc.file_id
    await update.message.reply_text(
        f"⚠️ <b>CONFIRM RESTORE?</b>\n\n"
        f"File: <code>{doc.file_name}</code>\n\n"
        f"⚡ This will replace the ENTIRE database!\n"
        f"Type <code>/confirmrestore</code> to proceed.",
        parse_mode="HTML"
    )


async def confirmrestore_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    if not await db.is_sudo(u_obj.id):
        await update.message.reply_text("🚫 Admin only command.")
        return

    if u_obj.id not in _pending_restore:
        await update.message.reply_text("❌ No pending restore. Use /restore first.")
        return

    file_id = _pending_restore.pop(u_obj.id)
    try:
        file = await ctx.bot.get_file(file_id)
        ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        bak  = os.path.join(BACKUP_DIR, f"pre_restore_{ts}.db")
        shutil.copy2(DB_PATH, bak)
        await file.download_to_drive(DB_PATH)
        await update.message.reply_text(
            f"✅ <b>Database Restored!</b>\n\n"
            f"🔄 Pre-restore backup: <code>{bak}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        log.error(f"Restore error: {e}")
        await update.message.reply_text(f"❌ Restore failed: {e}")

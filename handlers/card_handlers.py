# ════════════════════════════════════════════
# 🎴 Card Handlers: /catch /set /removeset /inventory
# ════════════════════════════════════════════
import asyncio
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from utils import (
    calculate_catch_chance, attempt_catch, rarity_stars,
    fmt_coins, safe_name, make_bar
)
from config import RARITY_CONFIG

log = logging.getLogger(__name__)

# Cooldown store
_catch_cd = {}
CATCH_COOLDOWN = 8   # seconds


def _check_cd(store: dict, user_id: int, seconds: int) -> int:
    import time
    now  = time.time()
    last = store.get(user_id, 0)
    if now - last < seconds:
        return int(seconds - (now - last)) + 1
    store[user_id] = now
    return 0


# ─────────────────────────────────────────────
# /catch <name>
# ─────────────────────────────────────────────
async def catch_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    wait = _check_cd(_catch_cd, u_obj.id, CATCH_COOLDOWN)
    if wait:
        await update.message.reply_text(f"⏳ Cooldown! Wait <b>{wait}s</b>", parse_mode="HTML")
        return

    # If name provided, search by name; else random
    card = None
    if ctx.args:
        name = " ".join(ctx.args)
        card = await db.get_card_by_name(name)
        if not card:
            await update.message.reply_text(
                f"❌ Card '<b>{name}</b>' not found!\n\nTry /catch without a name for a random card.",
                parse_mode="HTML"
            )
            return
    else:
        card = await db.get_random_card()
        if not card:
            await update.message.reply_text("❌ No cards in the database yet! Ask an admin to /upload cards.")
            return

    # Drop rate multiplier
    drop_rate = await db.get_drop_rate()

    # Check if player has Catch Boost item
    inventory = await db.get_user_inventory(u_obj.id)
    boost = 0.0
    for inv_item in inventory:
        if inv_item["effect"] in ("catch_boost_1h", "catch_boost_2h"):
            boost += 0.20
            break

    catch_chance = calculate_catch_chance(card["rarity"], drop_rate, boost)
    rarity_cfg   = RARITY_CONFIG.get(card["rarity"], RARITY_CONFIG["Common"])

    # Catching animation
    rarity_emoji = rarity_cfg["emoji"]
    anim_msg     = await update.message.reply_text(
        f"{rarity_emoji} <b>A wild card appeared!</b>\n\n"
        f"🃏 <b>{card['name']}</b>\n"
        f"🎬 {card['movie']}\n"
        f"⭐ {card['rarity']}\n\n"
        f"🎯 Catch rate: <b>{catch_chance*100:.0f}%</b>\n\n"
        f"⌛ Throwing ball...",
        parse_mode="HTML"
    )
    await asyncio.sleep(1.0)

    success = attempt_catch(catch_chance)

    if success:
        await db.add_card_to_user(u_obj.id, card["id"])
        xp_gain  = rarity_cfg["xp_reward"]
        xp_res   = await db.add_xp(u_obj.id, xp_gain)
        await db.update_mission_progress(u_obj.id, "catch", 1)
        new_achs = await db.check_achievements(u_obj.id)
        new_tits = await db.check_titles(u_obj.id)

        is_dup = await db.count_user_cards(u_obj.id) > 1

        if card["rarity"] == "Legendary":
            catch_fx = "🌟⚡🌟 <b>LEGENDARY CATCH!</b> 🌟⚡🌟"
        elif card["rarity"] == "Epic":
            catch_fx = "✨🟣 <b>EPIC CATCH!</b> 🟣✨"
        elif card["rarity"] == "Rare":
            catch_fx = "💙 <b>RARE CATCH!</b> 💙"
        else:
            catch_fx = "✅ <b>Caught!</b>"

        text = (
            f"{catch_fx}\n\n"
            f"╔══════════════════╗\n"
            f"  🃏 <b>{card['name']}</b>\n"
            f"  🎬 {card['movie']}\n"
            f"  {rarity_stars(card['rarity'])} {card['rarity']}\n"
            f"  🆔 Card ID: {card['id']}\n"
            f"╚══════════════════╝\n\n"
            f"✨ +{xp_gain} XP"
        )
        if xp_res["leveled_up"]:
            text += f"\n🎊 <b>LEVEL UP → {xp_res['new_level']}!</b>"
        for a in new_achs:
            text += f"\n{a['badge']} Achievement: <b>{a['name']}</b>"

        text += f"\n\n💡 Use <code>/set {card['id']}</code> to make it your profile card!"

        # Send with card image if available
        if card.get("file_id"):
            await anim_msg.delete()
            if card.get("file_type") == "video":
                await update.message.reply_video(
                    card["file_id"], caption=text, parse_mode="HTML"
                )
            else:
                await update.message.reply_photo(
                    card["file_id"], caption=text, parse_mode="HTML"
                )
        else:
            await anim_msg.edit_text(text, parse_mode="HTML")

    else:
        # Failed to catch
        text = (
            f"💨 <b>It got away!</b>\n\n"
            f"🃏 <b>{card['name']}</b> ({card['rarity']})\n"
            f"🎯 Catch rate was: {catch_chance*100:.0f}%\n\n"
            f"💡 Try again or use a Catch Boost from /shop!"
        )
        await anim_msg.edit_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /set <card_id>
# ─────────────────────────────────────────────
async def set_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user

    if not ctx.args:
        await update.message.reply_text(
            "❓ Usage: <code>/set &lt;card_id&gt;</code>\n"
            "Find card IDs in /inventory",
            parse_mode="HTML"
        )
        return

    try:
        card_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid card ID.")
        return

    await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    success = await db.set_favorite(u_obj.id, card_id)

    if not success:
        await update.message.reply_text(
            f"❌ You don't own card #{card_id}!\nCheck /inventory"
        )
        return

    card = await db.get_card(card_id)
    text = (
        f"⭐ <b>Favorite Card Set!</b>\n\n"
        f"🃏 <b>{card['name']}</b>\n"
        f"🎬 {card['movie']}\n"
        f"{rarity_stars(card['rarity'])} {card['rarity']}\n\n"
        f"📊 Your profile now shows this card!"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /removeset <card_id>
# ─────────────────────────────────────────────
async def removeset_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user

    if not ctx.args:
        await update.message.reply_text("❓ Usage: <code>/removeset &lt;card_id&gt;</code>", parse_mode="HTML")
        return

    try:
        card_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid card ID.")
        return

    await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    success = await db.remove_favorite(u_obj.id, card_id)

    if not success:
        await update.message.reply_text(f"❌ You don't own card #{card_id}.")
        return

    await update.message.reply_text(
        f"✅ Removed card #{card_id} from favorites.\n"
        f"Your profile is back to default display."
    )


# ─────────────────────────────────────────────
# /inventory
# ─────────────────────────────────────────────
async def inventory_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    # Default sort = rarity, page 1
    sort = "rarity"
    page = 1

    if ctx.args:
        for arg in ctx.args:
            if arg.isdigit():
                page = int(arg)
            elif arg in ("name", "rarity", "new", "old"):
                sort = arg

    cards      = await db.get_user_cards(u_obj.id, sort=sort, page=page)
    total      = await db.count_user_cards(u_obj.id)
    total_pages = max(1, (total + 11) // 12)

    if not cards and page == 1:
        await update.message.reply_text(
            "📦 Your collection is empty!\n\nUse /catch to start collecting cards!"
        )
        return

    # Group by rarity
    rarity_counts = {}
    for c in cards:
        r = c["rarity"]
        rarity_counts[r] = rarity_counts.get(r, 0) + 1

    header = (
        f"🃏 <b>CARD COLLECTION</b>  [{u_obj.first_name}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Total: <b>{total} cards</b>  |  Page {page}/{total_pages}\n"
        f"🔽 Sort: {sort}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    card_list = ""
    for c in cards:
        fav_star = "⭐" if c["is_favorite"] else "  "
        card_list += (
            f"{fav_star} [{c['id']:>3}] {rarity_stars(c['rarity'])} "
            f"<b>{c['name']}</b> — {c['movie']}\n"
        )

    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 /inventory {page+1} — next page\n"
        f"💡 /inventory rarity · name · new\n"
        f"💡 /set &lt;id&gt; to set favorite"
    )

    # Item inventory
    items     = await db.get_user_inventory(u_obj.id)
    item_text = ""
    if items:
        item_text = "\n🎒 <b>Item Inventory:</b>\n"
        for it in items:
            item_text += f"  • {it['name']} ×{it['quantity']}\n"

    full_text = header + card_list + item_text + footer
    await update.message.reply_text(full_text, parse_mode="HTML")

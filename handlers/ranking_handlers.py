# ════════════════════════════════════════════
# 📊 Ranking Handlers: /top /titles /missions /achievements
# ════════════════════════════════════════════
import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils import fmt_coins, rarity_stars, make_bar
from config import RARITY_CONFIG

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# /top
# ─────────────────────────────────────────────
async def top_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj    = update.effective_user
    await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    await db.ensure_weekly_entry(u_obj.id, u_obj.username or u_obj.first_name)

    top_all    = await db.get_top_users(10)
    top_weekly = await db.get_weekly_top(5)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    text = "🏆 <b>LEADERBOARD</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"
    text += "💰 <b>All-Time Top 10</b>\n\n"

    for i, u in enumerate(top_all):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name  = u.get("first_name") or u.get("username") or f"User#{u['user_id']}"
        is_me = " 👈" if u["user_id"] == u_obj.id else ""
        text += (
            f"{medal} <b>{name}</b>{is_me}\n"
            f"    💰 {u['coins']:,}  ·  Lv.{u['level']}\n"
        )

    text += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    text += "📅 <b>This Week's Top 5</b>\n\n"

    for i, u in enumerate(top_weekly[:5]):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name  = u.get("username") or f"User#{u['user_id']}"
        text += f"{medal} {name} — {u['weekly_coins']:,} coins earned\n"

    text += (
        "\n━━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 Weekly board resets every Monday!\n"
        "🏅 Weekly winner gets 2000 bonus coins!"
    )

    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /titles
# ─────────────────────────────────────────────
async def titles_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj   = update.effective_user
    user    = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    my_titles   = await db.get_user_titles(u_obj.id)
    earned_keys = {t["title_key"] for t in my_titles}
    active      = user.get("active_title", "t1")

    # Check for new titles
    new_titles = await db.check_titles(u_obj.id)

    from config import TITLES
    text = (
        f"🎖️ <b>TITLES</b>  [{u_obj.first_name}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Earned: <b>{len(earned_keys)}/{len(TITLES)}</b>\n\n"
    )

    for t in TITLES:
        if t["id"] in earned_keys:
            active_mark = " ✅ <i>(Active)</i>" if t["id"] == active else " ✅"
            text += f"{t['emoji']} <b>{t['name']}</b>{active_mark}\n"
            text += f"  └ {t['desc']}\n\n"
        else:
            text += f"🔒 ~~{t['name']}~~\n"
            text += f"  └ <i>{t['desc']}</i>\n\n"

    text += (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Earn titles by completing challenges!\n"
        "🔧 Set active title: <code>/settitle &lt;id&gt;</code>"
    )

    if new_titles:
        for nt in new_titles:
            text += f"\n\n🎉 New Title Unlocked: <b>{nt['name']}</b>!"

    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /missions
# ─────────────────────────────────────────────
async def missions_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj    = update.effective_user
    await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    missions = await db.get_user_missions(u_obj.id)

    daily_ms  = [m for m in missions if m.get("period") == "daily"]
    weekly_ms = [m for m in missions if m.get("period") == "weekly"]

    text = (
        f"📋 <b>MISSIONS</b>  [{u_obj.first_name}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 <b>Daily Missions</b>\n"
    )

    for m in daily_ms:
        prog  = m.get("progress", 0)
        req   = m.get("requirement", 1)
        done  = m.get("completed", 0)
        bar   = make_bar(prog, req, 8)
        check = "✅" if done else "⏳"
        text += (
            f"\n{check} <b>{m['name']}</b>  ({prog}/{req})\n"
            f"  {bar}  💰 +{m['reward']:,}\n"
            f"  <i>{m['description']}</i>\n"
        )

    text += f"\n━━━━━━━━━━━━━━━━━━━━━\n📆 <b>Weekly Missions</b>\n"
    for m in weekly_ms:
        prog  = m.get("progress", 0)
        req   = m.get("requirement", 1)
        done  = m.get("completed", 0)
        bar   = make_bar(prog, req, 8)
        check = "✅" if done else "⏳"
        text += (
            f"\n{check} <b>{m['name']}</b>  ({prog}/{req})\n"
            f"  {bar}  💰 +{m['reward']:,}\n"
            f"  <i>{m['description']}</i>\n"
        )

    text += "\n━━━━━━━━━━━━━━━━━━━━━\n💡 Missions reset daily/weekly automatically!"

    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /achievements
# ─────────────────────────────────────────────
async def achievements_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj   = update.effective_user
    await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    new_achs  = await db.check_achievements(u_obj.id)
    all_achs  = await db.get_user_achievements(u_obj.id)

    from config import ACHIEVEMENTS
    earned_keys = {a["ach_key"] for a in all_achs}

    text = (
        f"🏅 <b>ACHIEVEMENTS</b>  [{u_obj.first_name}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Earned: <b>{len(earned_keys)}/{len(ACHIEVEMENTS)}</b>\n\n"
    )

    for a in ACHIEVEMENTS:
        if a["id"] in earned_keys:
            earned_at = next((x["earned_at"][:10] for x in all_achs if x["ach_key"] == a["id"]), "?")
            text += f"{a['badge']} <b>{a['name']}</b> ✅\n"
            text += f"  └ {a['desc']}  <i>({earned_at})</i>\n\n"
        else:
            text += f"🔒 <b>{a['name']}</b>\n"
            text += f"  └ <i>{a['desc']}</i>\n\n"

    if new_achs:
        text += "\n🎉 <b>New Achievements Today:</b>\n"
        for a in new_achs:
            text += f"  {a['badge']} {a['name']}\n"

    await update.message.reply_text(text, parse_mode="HTML")

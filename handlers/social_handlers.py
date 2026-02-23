# ════════════════════════════════════════════
# 👥 Social Handlers: /givecoin /marry /divorce /friends
# ════════════════════════════════════════════
import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils import fmt_coins, safe_name, mention

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# /givecoin <amount>
# ─────────────────────────────────────────────
async def givecoin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❓ Reply to a user's message with <code>/givecoin &lt;amount&gt;</code>",
            parse_mode="HTML"
        )
        return

    if not ctx.args:
        await update.message.reply_text("❓ Specify an amount: <code>/givecoin &lt;amount&gt;</code>", parse_mode="HTML")
        return

    target = update.message.reply_to_message.from_user
    if target.id == u_obj.id:
        await update.message.reply_text("❌ You can't give coins to yourself!")
        return
    if target.is_bot:
        await update.message.reply_text("❌ Can't give coins to a bot!")
        return

    try:
        amount = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be positive.")
        return

    sender = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    await db.get_or_create_user(target.id, target.username or "", target.first_name or "")

    result = await db.give_coins(u_obj.id, target.id, amount)
    if not result["success"]:
        await update.message.reply_text(f"❌ {result['message']}")
        return

    await db.update_mission_progress(u_obj.id, "give", amount)
    new_achs = await db.check_achievements(u_obj.id)

    text = (
        f"💸 <b>COINS TRANSFERRED!</b>\n\n"
        f"📤 From: <b>{u_obj.first_name}</b>\n"
        f"📥 To:   <b>{target.first_name}</b>\n"
        f"💰 Amount: <b>{fmt_coins(amount)}</b>\n\n"
        f"💡 Transaction logged!"
    )
    await update.message.reply_text(text, parse_mode="HTML")
    if new_achs:
        for a in new_achs:
            await update.message.reply_text(f"{a['badge']} Achievement Unlocked: <b>{a['name']}</b>!", parse_mode="HTML")


# ─────────────────────────────────────────────
# /marry (Reply to target)
# ─────────────────────────────────────────────
async def marry_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    if user.get("married_to"):
        partner = await db.get_user(user["married_to"])
        pname   = partner.get("first_name") or partner.get("username") if partner else "Unknown"
        await update.message.reply_text(
            f"💍 You're already married to <b>{pname}</b>!\n"
            f"Use /divorce first to get divorced.",
            parse_mode="HTML"
        )
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "💍 Reply to someone's message to propose!\n"
            "Usage: Reply + <code>/marry</code>",
            parse_mode="HTML"
        )
        return

    target = update.message.reply_to_message.from_user
    if target.id == u_obj.id:
        await update.message.reply_text("❌ You can't marry yourself! 😅")
        return
    if target.is_bot:
        await update.message.reply_text("❌ Bots can't be married! 🤖")
        return

    t_user = await db.get_or_create_user(target.id, target.username or "", target.first_name or "")
    if t_user.get("married_to"):
        await update.message.reply_text(
            f"💔 <b>{target.first_name}</b> is already married to someone else!",
            parse_mode="HTML"
        )
        return

    await db.marry(u_obj.id, target.id)

    # Both users get friend bonus XP
    await db.add_xp(u_obj.id, 50)
    await db.add_xp(target.id, 50)
    await db.add_friend(u_obj.id, target.id)

    new_achs_s = await db.check_achievements(u_obj.id)
    new_achs_t = await db.check_achievements(target.id)
    await db.check_titles(u_obj.id)
    await db.check_titles(target.id)

    text = (
        f"💍 <b>CONGRATULATIONS!</b> 💍\n\n"
        f"💑 <b>{u_obj.first_name}</b> 💕 <b>{target.first_name}</b>\n\n"
        f"You are now married! 🎊\n"
        f"• Both receive +50 XP\n"
        f"• Couple daily bonus active!\n\n"
        f"👫 <i>May your bond last forever!</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /divorce
# ─────────────────────────────────────────────
async def divorce_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    if not user.get("married_to"):
        await update.message.reply_text("💔 You're not married to anyone!")
        return

    partner_id = await db.divorce(u_obj.id)
    partner    = await db.get_user(partner_id) if partner_id else None
    pname      = partner.get("first_name") or partner.get("username") if partner else "your partner"

    text = (
        f"💔 <b>Divorced</b>\n\n"
        f"You and <b>{pname}</b> are no longer married.\n"
        f"Couple bonus removed.\n\n"
        f"💡 You're single again. Start fresh! 🌱"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /friends
# ─────────────────────────────────────────────
async def friends_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj   = update.effective_user
    user    = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")
    friends = await db.get_friends(u_obj.id)

    if not friends:
        text = (
            f"👥 <b>FRIENDS LIST</b>\n\n"
            f"You have no friends yet! 😢\n\n"
            f"💡 You become friends automatically when:\n"
            f"  • You /marry someone\n"
            f"  • You /givecoin to someone 5+ times\n"
            f"  • You're in the same /top leaderboard"
        )
        await update.message.reply_text(text, parse_mode="HTML")
        return

    text = (
        f"👥 <b>FRIENDS LIST</b>  [{u_obj.first_name}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Total: <b>{len(friends)} friends</b>\n\n"
    )

    for i, f in enumerate(friends, 1):
        fname = f.get("first_name") or f.get("username") or f"User #{f['user_id']}"
        title_emoji = "🌱"  # default
        text += f"<b>{i}.</b> {fname}  ·  Lv.{f['level']} {title_emoji}\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Friend interactions give bonus XP!"
    )

    new_achs = await db.check_achievements(u_obj.id)
    await update.message.reply_text(text, parse_mode="HTML")

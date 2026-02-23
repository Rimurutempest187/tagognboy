# ════════════════════════════════════════════
# 🎮 Game Handlers: /slots /basket /wheel
# ════════════════════════════════════════════
import asyncio
import logging
import random
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils import (
    spin_slots, basket_shot, basket_animation,
    spin_wheel, wheel_animation, fmt_coins, safe_name
)

log = logging.getLogger(__name__)

# Cooldowns: user_id -> timestamp
_slot_cd   = {}
_basket_cd = {}
_wheel_cd  = {}

SLOT_COOLDOWN   = 5   # seconds
BASKET_COOLDOWN = 10
WHEEL_COOLDOWN  = 15


def _check_cd(store: dict, user_id: int, seconds: int) -> int:
    import time
    now  = time.time()
    last = store.get(user_id, 0)
    diff = now - last
    if diff < seconds:
        return int(seconds - diff) + 1
    store[user_id] = now
    return 0


# ─────────────────────────────────────────────
# /slots <amount>
# ─────────────────────────────────────────────
async def slots_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    if not ctx.args:
        await update.message.reply_text(
            "🎰 Usage: <code>/slots &lt;amount&gt;</code>\nMin: 50 coins",
            parse_mode="HTML"
        )
        return

    wait = _check_cd(_slot_cd, u_obj.id, SLOT_COOLDOWN)
    if wait:
        await update.message.reply_text(f"⏳ Cooldown! Wait <b>{wait}s</b>", parse_mode="HTML")
        return

    try:
        amount = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    if amount < 50:
        await update.message.reply_text("❌ Minimum bet is 50 coins.")
        return
    if user["coins"] < amount:
        await update.message.reply_text(f"❌ Not enough coins! You have {fmt_coins(user['coins'])}")
        return

    # Deduct bet
    await db.add_coins(u_obj.id, -amount, tx_type="slots_bet")

    # Spin
    result = spin_slots()

    # Animation
    spin_msg = await update.message.reply_text("🎰 Spinning...\n\n⌛ | ? | ? | ? |")
    await asyncio.sleep(0.7)
    await spin_msg.edit_text(f"🎰 Spinning...\n\n{result['display']}")
    await asyncio.sleep(0.5)

    # Calculate winnings
    winnings  = int(amount * result["multiplier"])
    net       = winnings - amount
    is_win    = result["result"] != "lose"
    is_jack   = result["result"] == "jackpot"

    if is_win:
        await db.add_coins(u_obj.id, winnings, tx_type="slots_win")
        await db.update_mission_progress(u_obj.id, "slots", 1)

    if is_jack:
        await db.update_user(
            u_obj.id,
            jackpots=user["jackpots"] + 1,
            slots_wins=user["slots_wins"] + winnings
        )
    elif is_win:
        await db.update_user(u_obj.id, slots_wins=user["slots_wins"] + winnings)

    xp_gain = 10 if is_win else 5
    xp_res  = await db.add_xp(u_obj.id, xp_gain)

    new_achs = await db.check_achievements(u_obj.id)
    new_tits = await db.check_titles(u_obj.id)

    # Build result message
    if is_jack:
        header = "🎊🎰 JACKPOT!!! 🎰🎊"
        outcome_emoji = "💥"
    elif result["result"] in ("super", "mega", "triple"):
        header = f"🎉 {result['result'].upper()} WIN!"
        outcome_emoji = "🌟"
    elif result["result"] == "pair":
        header = "✅ Pair Match!"
        outcome_emoji = "💫"
    else:
        header = "😔 No Match"
        outcome_emoji = "💨"

    text = (
        f"{header}\n\n"
        f"╔══════════════════╗\n"
        f"  🎰 {result['display']}\n"
        f"╚══════════════════╝\n\n"
        f"💸 Bet:     <b>{fmt_coins(amount)}</b>\n"
    )
    if is_win:
        text += (
            f"{outcome_emoji} Win:     <b>+{fmt_coins(winnings)}</b>\n"
            f"📈 Profit: <b>+{fmt_coins(net)}</b>  ({result['multiplier']}x)\n"
        )
    else:
        text += f"💔 Lost:   <b>-{fmt_coins(amount)}</b>\n"

    text += f"\n✨ +{xp_gain} XP"

    if xp_res["leveled_up"]:
        text += f"\n🎊 <b>LEVEL UP → {xp_res['new_level']}!</b>"

    if new_achs:
        for a in new_achs:
            text += f"\n{a['badge']} Achievement: <b>{a['name']}</b>"

    if is_jack:
        text += "\n\n🎆🎆 <b>LEGENDARY JACKPOT!</b> 🎆🎆"

    await spin_msg.edit_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /basket <amount>
# ─────────────────────────────────────────────
async def basket_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    if not ctx.args:
        await update.message.reply_text(
            "🏀 Usage: <code>/basket &lt;amount&gt;</code>\nMin: 50 coins · 5 shots per game",
            parse_mode="HTML"
        )
        return

    wait = _check_cd(_basket_cd, u_obj.id, BASKET_COOLDOWN)
    if wait:
        await update.message.reply_text(f"⏳ Cooldown! Wait <b>{wait}s</b>", parse_mode="HTML")
        return

    try:
        amount = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    if amount < 50:
        await update.message.reply_text("❌ Minimum bet: 50 coins.")
        return
    if user["coins"] < amount:
        await update.message.reply_text(f"❌ Not enough coins! You have {fmt_coins(user['coins'])}")
        return

    await db.add_coins(u_obj.id, -amount, tx_type="basket_bet")

    # Play 5 shots
    shots = 5
    combo = 0
    max_combo = 0
    total_pts = 0
    shot_log  = []

    for i in range(shots):
        res = basket_shot(combo)
        anim = basket_animation(res["hit"])
        if res["hit"]:
            combo += 1
            total_pts += res["points"]
            shot_str = f"Shot {i+1}: {anim} +{res['points']}pts"
            if combo >= 3:
                shot_str += f" 🔥×{combo}"
        else:
            combo = 0
            shot_str = f"Shot {i+1}: {anim}"
        max_combo = max(max_combo, combo)
        shot_log.append(shot_str)

    # Score multiplier based on points
    # Max possible = 5*3 = 15 pts
    score_pct = total_pts / 15
    if score_pct >= 0.9:
        multiplier = 3.0
    elif score_pct >= 0.7:
        multiplier = 2.0
    elif score_pct >= 0.5:
        multiplier = 1.5
    elif score_pct >= 0.3:
        multiplier = 1.0
    else:
        multiplier = 0.5

    winnings = int(amount * multiplier)
    net      = winnings - amount
    await db.add_coins(u_obj.id, winnings, tx_type="basket_win")

    # Update best combo
    if max_combo > user["best_combo"]:
        await db.update_user(u_obj.id, best_combo=max_combo)

    xp_gain = 10 + (total_pts * 2)
    xp_res  = await db.add_xp(u_obj.id, xp_gain)
    await db.update_mission_progress(u_obj.id, "basket", 1)
    await db.update_mission_progress(u_obj.id, "bscore", total_pts)
    new_achs = await db.check_achievements(u_obj.id)
    new_tits = await db.check_titles(u_obj.id)

    shots_text = "\n".join(shot_log)

    text = (
        f"🏀 <b>BASKETBALL GAME</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{shots_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Score:      <b>{total_pts} pts</b>\n"
        f"🔥 Best Combo: <b>×{max_combo}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 Bet:     {fmt_coins(amount)}\n"
        f"🏆 Return:  {multiplier}x = <b>{fmt_coins(winnings)}</b>\n"
    )

    if net > 0:
        text += f"📈 Profit:  <b>+{fmt_coins(net)}</b>\n"
    elif net < 0:
        text += f"📉 Loss:    <b>{fmt_coins(net)}</b>\n"
    else:
        text += f"🤝 Break even!\n"

    text += f"\n✨ +{xp_gain} XP"
    if xp_res["leveled_up"]:
        text += f"\n🎊 <b>LEVEL UP → {xp_res['new_level']}!</b>"
    if new_achs:
        for a in new_achs:
            text += f"\n{a['badge']} Achievement: <b>{a['name']}</b>"

    if max_combo >= 5:
        text += f"\n\n🔥🏀 <b>COMBO MASTER! ×{max_combo}</b>"

    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# /wheel <amount>
# ─────────────────────────────────────────────
async def wheel_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u_obj = update.effective_user
    user  = await db.get_or_create_user(u_obj.id, u_obj.username or "", u_obj.first_name or "")

    if not ctx.args:
        await update.message.reply_text(
            "🎡 Usage: <code>/wheel &lt;amount&gt;</code>\nMin: 100 coins",
            parse_mode="HTML"
        )
        return

    wait = _check_cd(_wheel_cd, u_obj.id, WHEEL_COOLDOWN)
    if wait:
        await update.message.reply_text(f"⏳ Cooldown! Wait <b>{wait}s</b>", parse_mode="HTML")
        return

    try:
        amount = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount.")
        return

    if amount < 100:
        await update.message.reply_text("❌ Minimum spin cost: 100 coins.")
        return
    if user["coins"] < amount:
        await update.message.reply_text(f"❌ Insufficient coins! You have {fmt_coins(user['coins'])}")
        return

    await db.add_coins(u_obj.id, -amount, tx_type="wheel_cost")

    # Spin animation
    spin_msg = await update.message.reply_text(
        "🎡 <b>WHEEL OF FORTUNE</b>\n\n🌀 Spinning...", parse_mode="HTML"
    )
    await asyncio.sleep(0.8)
    await spin_msg.edit_text(
        "🎡 <b>WHEEL OF FORTUNE</b>\n\n💫 Almost there...", parse_mode="HTML"
    )
    await asyncio.sleep(0.7)

    prize = spin_wheel()

    # Apply prize
    result_text = ""
    if prize["type"] == "coins":
        await db.add_coins(u_obj.id, prize["value"], tx_type="wheel_prize",
                          note=prize["name"])
        net = prize["value"] - amount
        result_text = (
            f"💰 Won: <b>+{fmt_coins(prize['value'])}</b>\n"
            f"{'📈' if net>0 else '📉'} Net: <b>{'+' if net>=0 else ''}{fmt_coins(net)}</b>"
        )
    elif prize["type"] == "xp":
        xp_res = await db.add_xp(u_obj.id, prize["value"])
        result_text = f"✨ Won: <b>+{prize['value']} XP!</b>"
        if xp_res.get("leveled_up"):
            result_text += f"\n🎊 <b>LEVEL UP → {xp_res['new_level']}!</b>"
    elif prize["type"] == "card":
        # Give a random card from the DB
        card = await db.get_random_card()
        if card:
            await db.add_card_to_user(u_obj.id, card["id"])
            from utils import rarity_stars
            result_text = (
                f"🃏 Rare Card Drop!\n"
                f"  {rarity_stars(card['rarity'])} <b>{card['name']}</b> [{card['movie']}]"
            )
        else:
            await db.add_coins(u_obj.id, 500, tx_type="wheel_fallback")
            result_text = "🃏 No cards available, got 500 coins instead!"
    elif prize["type"] == "item":
        await db.add_coins(u_obj.id, 300, tx_type="wheel_item_fallback")
        result_text = "🎁 Lucky Item! +300 coins!"

    xp_res2 = await db.add_xp(u_obj.id, 15)
    await db.update_mission_progress(u_obj.id, "wheel", 1)
    new_achs = await db.check_achievements(u_obj.id)
    new_tits = await db.check_titles(u_obj.id)

    text = (
        f"🎡 <b>WHEEL RESULT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Prize: <b>{prize['name']}</b>\n\n"
        f"{result_text}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💸 Cost: {fmt_coins(amount)}\n"
        f"✨ +15 XP"
    )

    if xp_res2.get("leveled_up"):
        text += f"\n🎊 <b>LEVEL UP → {xp_res2['new_level']}!</b>"
    for a in new_achs:
        text += f"\n{a['badge']} Achievement: <b>{a['name']}</b>"

    await spin_msg.edit_text(text, parse_mode="HTML")

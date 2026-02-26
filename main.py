import logging
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

logging.basicConfig(level=logging.INFO)

# ✅ Secrets (KEINE Default Werte → verhindert Crash)
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

# ===== DATABASE =====
def init_db():
    conn = sqlite3.connect("exchange.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        ltc_address TEXT,
        psc_code TEXT,
        amount REAL,
        fee REAL,
        final REAL,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ===== USER STATES =====
USER_STATE = {}

STATE_LTC = "LTC"
STATE_PSC = "PSC"
STATE_AMOUNT = "AMOUNT"
STATE_PHOTO = "PHOTO"

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔄 Exchange starten", callback_data='start_exchange')],
        [InlineKeyboardButton("ℹ️ Info", callback_data='info')]
    ]
    await update.message.reply_text(
        "👋 Willkommen beim Exchange Bot 🚀",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== BUTTON HANDLER =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_exchange":
        USER_STATE[query.from_user.id] = {"state": STATE_LTC}
        await query.edit_message_text("🪙 Sende deine LTC Adresse")

    elif query.data == "info":
        await query.edit_message_text("💎 Tausche PaySafeCard → LTC")

    elif query.data.startswith("accept_") or query.data.startswith("decline_"):
        if query.from_user.id != ADMIN_ID:
            return

        action, order_id = query.data.split("_")
        conn = sqlite3.connect("exchange.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
        row = cursor.fetchone()

        if row:
            user_id = row[0]
            if action == "accept":
                await context.bot.send_message(user_id, "✅ Anfrage akzeptiert")
                cursor.execute("UPDATE orders SET status='ACCEPTED' WHERE id=?", (order_id,))
            else:
                await context.bot.send_message(user_id, "❌ Anfrage abgelehnt")
                cursor.execute("UPDATE orders SET status='DECLINED' WHERE id=?", (order_id,))

        conn.commit()
        conn.close()
        await query.edit_message_text("Erledigt ✅")

# ===== MESSAGE HANDLER =====
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in USER_STATE:
        return

    state = USER_STATE[user_id]["state"]

    if state == STATE_LTC:
        USER_STATE[user_id]["ltc"] = update.message.text
        USER_STATE[user_id]["state"] = STATE_PSC
        await update.message.reply_text("💳 Sende PSC Code")

    elif state == STATE_PSC:
        USER_STATE[user_id]["psc"] = update.message.text
        USER_STATE[user_id]["state"] = STATE_AMOUNT
        await update.message.reply_text("💰 Betrag?")

    elif state == STATE_AMOUNT:
        try:
            amount = float(update.message.text)
            fee = round(amount * 0.20, 2)
            final = amount - fee

            USER_STATE[user_id]["amount"] = amount
            USER_STATE[user_id]["fee"] = fee
            USER_STATE[user_id]["final"] = final
            USER_STATE[user_id]["state"] = STATE_PHOTO

            await update.message.reply_text(
                f"Betrag: {amount}€\nFee: {fee}€\nAuszahlung: {final}€\n📸 Screenshot senden"
            )
        except:
            await update.message.reply_text("Nur Zahl eingeben")

    elif state == STATE_PHOTO:
        if update.message.photo:
            conn = sqlite3.connect("exchange.db")
            cursor = conn.cursor()

            data = USER_STATE[user_id]

            cursor.execute("""
            INSERT INTO orders (user_id, username, ltc_address, psc_code, amount, fee, final, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                update.effective_user.username,
                data["ltc"],
                data["psc"],
                data["amount"],
                data["fee"],
                data["final"],
                "PENDING"
            ))

            order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            keyboard = [[
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{order_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"decline_{order_id}")
            ]]

            await context.bot.send_photo(
                ADMIN_ID,
                update.message.photo[-1].file_id,
                caption=f"Neue Anfrage #{order_id}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            await update.message.reply_text("⏳ Anfrage gesendet")

            del USER_STATE[user_id]

# ===== MAIN =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO, message_handler))

    print("Bot läuft 🚀")
    app.run_polling()

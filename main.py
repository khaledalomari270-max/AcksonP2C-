import logging
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8779721069:AAHKxXqR27JxK8CgTCIRBGfay-q9syAeP7o")
ADMIN_ID = os.environ.get("ADMIN_ID", "7488274640")

if not TOKEN or not ADMIN_ID:
    print("Error: TELEGRAM_BOT_TOKEN and ADMIN_ID must be set in Secrets.")
    exit(1)

ADMIN_ID = int(ADMIN_ID)

# Database Setup
def init_db():
    conn = sqlite3.connect("exchange.db", check_same_thread=False)
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

# States
USER_STATE = {} 

# Constants
STATE_WAITING_LTC = "WAITING_LTC"
STATE_WAITING_PSC = "WAITING_PSC"
STATE_WAITING_AMOUNT = "WAITING_AMOUNT"
STATE_WAITING_PHOTO = "WAITING_PHOTO"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"👋 Willkommen bei **AcksonP2C**!\n\n"
        f"Wir bieten einen sicheren Exchange von **PaySafeCards** zu **Litecoin (LTC)** an. 🚀\n\n"
        f"💎 **Gebühren: 20%**\n"
        f"👤 Service by @A_Ackson_Backup\n"
        f"🛠 Support @A_Ackson_Backup\n\n"
        f"Wähle eine Option aus dem Menü unten:"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Exchange starten", callback_data='start_exchange')],
        [InlineKeyboardButton("ℹ️ Info / Support", callback_data='support_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'start_exchange':
        USER_STATE[query.from_user.id] = {'state': STATE_WAITING_LTC}
        await query.edit_message_text(
            "🪙 **Litecoin (LTC) Exchange**\n\n"
            "Bitte sende mir jetzt deine **Litecoin (LTC) Adresse**, an die das Guthaben gesendet werden soll. 📥",
            parse_mode='Markdown'
        )
    elif query.data == 'support_info':
        await query.edit_message_text(
            "💎 **AcksonP2C Service**\n\n"
            "Wir tauschen deine PaySafeCards schnell und sicher in LTC um.\n\n"
            "Gebühren: 20%\n"
            "👤 Admin: @A_Ackson_Backup\n"
            "📢 Support: @A_Ackson_Backup\n\n"
            "Klicke auf /start um zum Hauptmenü zu gelangen.",
            parse_mode='Markdown'
        )
    elif query.data.startswith('accept_') or query.data.startswith('decline_'):
        if query.from_user.id != ADMIN_ID:
            return

        action, order_id = query.data.split('_')
        order_id = int(order_id)

        conn = sqlite3.connect("exchange.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, final FROM orders WHERE id=?", (order_id,))
        row = cursor.fetchone()

        if row:
            target_user_id, final_amount = row
            if action == 'accept':
                cursor.execute("UPDATE orders SET status='ACCEPTED' WHERE id=?", (order_id,))
                await context.bot.send_message(target_user_id, f"✅ Deine Anfrage wurde vom Admin **akzeptiert**. Die Auszahlung von {final_amount}€ in LTC erfolgt in Kürze! 🚀")
                await query.edit_message_text(f"✅ Du hast die Anfrage #{order_id} **akzeptiert**.")
            else:
                cursor.execute("UPDATE orders SET status='DECLINED' WHERE id=?", (order_id,))
                await context.bot.send_message(target_user_id, "❌ Deine Anfrage wurde vom Admin **abgelehnt**. Bei Fragen wende dich an den Support.")
                await query.edit_message_text(f"❌ Du hast die Anfrage #{order_id} **abgelehnt**.")
        conn.commit()
        conn.close()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in USER_STATE:
        return

    state_data = USER_STATE[user_id]
    current_state = state_data.get('state')

    if current_state == STATE_WAITING_LTC:
        state_data['ltc_address'] = update.message.text
        state_data['state'] = STATE_WAITING_PSC
        await update.message.reply_text(
            "💳 Super! Bitte sende mir nun den **PaySafeCard Code**. 📝",
            parse_mode='Markdown'
        )

    elif current_state == STATE_WAITING_PSC:
        state_data['psc_code'] = update.message.text
        state_data['state'] = STATE_WAITING_AMOUNT
        await update.message.reply_text(
            "💰 Wie hoch ist der **Betrag** der PaySafeCard? (nur Zahl, z.B. 25)",
            parse_mode='Markdown'
        )

    elif current_state == STATE_WAITING_AMOUNT:
        try:
            amount = float(update.message.text)
            if amount <= 0: raise ValueError
            fee = round(amount * 0.20, 2)
            final = round(amount - fee, 2)
            state_data['amount'] = amount
            state_data['fee'] = fee
            state_data['final'] = final
            state_data['state'] = STATE_WAITING_PHOTO
            await update.message.reply_text(
                f"📊 **Zusammenfassung:**\n"
                f"Betrag: {amount}€\n"
                f"Gebühr (20%): {fee}€\n"
                f"Auszahlung: {final}€ in LTC\n\n"
                f"📸 Bitte sende mir jetzt einen **Screenshot vom Bon** der PaySafeCard. 🖼",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Bitte gib einen gültigen Betrag ein (nur Zahl).")

    elif current_state == STATE_WAITING_PHOTO:
        logging.info(f"Received message in STATE_WAITING_PHOTO from {user_id}")
        if update.message.photo or update.message.document:
            if update.message.photo:
                photo_file_id = update.message.photo[-1].file_id
                logging.info(f"Photo received: {photo_file_id}")
            else:
                photo_file_id = update.message.document.file_id
                logging.info(f"Document received: {photo_file_id}")

            # Save to Database
            conn = sqlite3.connect("exchange.db")
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO orders (user_id, username, ltc_address, psc_code, amount, fee, final, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, update.effective_user.username, state_data['ltc_address'], 
                  state_data['psc_code'], state_data['amount'], state_data['fee'], 
                  state_data['final'], 'PENDING'))
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Send to Admin
            admin_text = (
                f"📥 *Neue Exchange Anfrage #{order_id}*\n\n"
                f"👤 *User:* @{update.effective_user.username} (ID: {user_id})\n"
                f"🪙 *LTC Addy:* `{state_data['ltc_address']}`\n"
                f"💳 *PSC Code:* `{state_data['psc_code']}`\n"
                f"💰 *Betrag:* {state_data['amount']}€\n"
                f"💸 *Fee (20%):* {state_data['fee']}€\n"
                f"✅ *Auszahlung:* {state_data['final']}€\n\n"
                f"Bitte prüfe den Screenshot und entscheide:"
            )

            keyboard = [
                [
                    InlineKeyboardButton("✅ Akzeptieren", callback_data=f"accept_{order_id}"),
                    InlineKeyboardButton("❌ Ablehnen", callback_data=f"decline_{order_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=photo_file_id,
                    caption=admin_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await context.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=photo_file_id,
                    caption=admin_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

            await update.message.reply_text(
                "⏳ Deine Anfrage wurde an den Admin weitergeleitet. Bitte warte auf eine Bestätigung. 🙏",
                parse_mode='Markdown'
            )
            del USER_STATE[user_id]
        else:
            await update.message.reply_text("⚠️ Bitte sende einen Screenshot (Foto) vom Bon.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, message_handler))

    print("Bot is running...")
    application.run_polling()

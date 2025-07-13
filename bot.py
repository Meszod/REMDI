import asyncio
import os
import re
import random

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackQueryHandler, ContextTypes
)

# === TELEGRAM API VA BOT MA'LUMOTLARI ===
api_id = 24305108
api_hash = 'a714fb632fadadc3aea1b8838263241f'
bot_token = '8004808341:AAE7gvW_3tdnLwX_oXp5oEtclnGzCTFdipA'
admin_id = 7105959922 # Adminning Telegram user ID sini o'zgartiring (masalan, o'zingizning ID)

# === FOYDALANUVCHI HOLATLARI ===
PHONE, CODE, PASSWORD, BOT_NAME = range(4)

# === FOYDALANUVCHI MA'LUMOTLARI ===
user_data = {}  # user_id: {"accounts": [...], "bot_username": str, "tasks": [], "approved": bool}
approved_users = set()  # Ruxsat berilgan foydalanuvchilar

# === CAPTCHA EMOJI MOSLIGI ===
emoji_map = {
    'Виноград': '🍇', 'Ананас': '🍍', 'Яблоко': '🍎', 'Клубника': '🍓', 'Арбуз': '🍉',
    'Банан': '🍌', 'Лимон': '🍋', 'Вишня': '🍒', 'Персик': '🍑', 'Манго': '🥭',
    'Груша': '🍐', 'Слива': '🫐', 'Черника': '🫐', 'Гранат': '🧃', 'Апельсин': '🍊',
    'Дыня': '🍈', 'Папайя': '🥭', 'Киви': '🥝', 'Инжир': '🍈', 'Огурец': '🥒',
    'Помидор': '🍅', 'Морковь': '🥕', 'Кукуруза': '🌽', 'Картофель': '🥔',
    'Баклажан': '🍆', 'Перец': '🫑', 'Чеснок': '🧄', 'Лук': '🧅', 'Горошек': '🫛',
    'Брокколи': '🥦', 'Салат': '🥬', 'Капуста': '🥬', 'Тыква': '🎃', 'Мёд': '🍯',
    'Кокос': '🥥', 'Авокадо': '🥑', 'Гриб': '🍄'
}

# === SESSION SAQLASH VA YUKLASH ===
def get_session_path(user_id, acc_index):
    return f"sessions/{user_id}_{acc_index}.session"

def save_session_file(user_id, index, session_str):
    os.makedirs("sessions", exist_ok=True)
    with open(get_session_path(user_id, index), "w") as f:
        f.write(session_str)

def load_all_sessions(user_id):
    clients = []
    index = 0
    while True:
        path = get_session_path(user_id, index)
        if not os.path.exists(path):
            break
        with open(path, "r") as f:
            session_str = f.read()
        client = TelegramClient(StringSession(session_str), api_id, api_hash)
        asyncio.run(client.connect())
        if asyncio.run(client.is_user_authorized()):
            clients.append(client)
        else:
            asyncio.run(client.disconnect())
        index += 1
    return clients

# === FLASK APP FOR PING (Faqat ping uchun) ===
from flask import Flask
app = Flask(__name__)

@app.route('/ping', methods=['GET'])
def ping():
    return "Bot is alive", 200

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"accounts": [], "bot_username": None, "tasks": [], "approved": False}
    if not user_data[user_id]["approved"]:
        await update.message.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return
    keyboard = [
        [InlineKeyboardButton("➕ Akkount qo‘shish", callback_data="add_account")],
        [InlineKeyboardButton("🤖 Bot qo‘shish", callback_data="add_bot")],
        [InlineKeyboardButton("▶️ Start Clicker", callback_data="start_click")],
        [InlineKeyboardButton("🛑 Stop Clicker", callback_data="stop_click")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Quyidagilardan birini tanlang:", reply_markup=reply_markup)

# === /approve komandasi (faqat admin uchun) ===
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != admin_id:
        await update.message.reply_text("⛔ Siz admin emassiz! Ushbu komandani faqat admin ishlatishi mumkin.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Foydalanuvchi ID sini kiriting: /approve <user_id>")
        return
    try:
        target_user_id = int(context.args[0])
        if target_user_id in user_data:
            user_data[target_user_id]["approved"] = True
            approved_users.add(target_user_id)
            await update.message.reply_text(f"✅ Foydalanuvchi {target_user_id} ga ruxsat berildi!")
        else:
            await update.message.reply_text(f"❌ Foydalanuvchi {target_user_id} topilmadi.")
    except ValueError:
        await update.message.reply_text("❌ Iltimos, to‘g‘ri user ID kiriting.")

# === CALLBACK HANDLER ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"accounts": [], "bot_username": None, "tasks": [], "approved": False}
    if not user_data[user_id]["approved"]:
        await query.edit_message_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return
    if query.data == "add_account":
        await query.edit_message_text("📱 Telefon raqamingizni kiriting (masalan: +9989XXXXXX):")
        return PHONE
    elif query.data == "add_bot":
        await query.edit_message_text("🤖 Clicker ishlatiladigan bot username'sini kiriting (masalan: @patrickstarsrobot):")
        return BOT_NAME
    elif query.data == "start_click":
        await start_click(update, context, from_callback=True)
    elif query.data == "stop_click":
        await stop_click(update, context, from_callback=True)

# === PHONE / CODE / PASSWORD ===
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_data[user_id]["approved"]:
        await update.message.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return ConversationHandler.END
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        await client.send_code_request(phone)
    except Exception as e:
        await update.message.reply_text(f"❌ Kod yuborishda xatolik: {e}")
        await client.disconnect()
        return ConversationHandler.END
    context.user_data['client'] = client
    await update.message.reply_text("📩 Kodni kiriting:")
    return CODE

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_data[user_id]["approved"]:
        await update.message.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return ConversationHandler.END
    code = update.message.text.strip()
    client = context.user_data['client']
    phone = context.user_data['phone']
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 2FA parolni kiriting:")
        return PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ Kirish xatosi: {e}")
        await client.disconnect()
        return ConversationHandler.END
    await finalize_login(update, client)
    return ConversationHandler.END

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_data[user_id]["approved"]:
        await update.message.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return ConversationHandler.END
    password = update.message.text.strip()
    client = context.user_data['client']
    try:
        await client.sign_in(password=password)
    except Exception as e:
        await update.message.reply_text(f"❌ Parol xato: {e}")
        await client.disconnect()
        return ConversationHandler.END
    await finalize_login(update, client)
    return ConversationHandler.END

async def finalize_login(update, client):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"accounts": [], "bot_username": None, "tasks": [], "approved": False}
    acc_index = len(user_data[user_id]["accounts"])
    session_str = client.session.save()
    save_session_file(user_id, acc_index, session_str)
    user_data[user_id]["accounts"].append(client)
    await update.message.reply_text("✅ Akkount qo‘shildi. /start orqali davom eting.")

# === BOT USERNAME ===
async def get_bot_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_data[user_id]["approved"]:
        await update.message.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return ConversationHandler.END
    bot_name = update.message.text.strip()
    if not bot_name.startswith("@"): bot_name = "@" + bot_name
    if user_id not in user_data:
        user_data[user_id] = {"accounts": [], "bot_username": None, "tasks": [], "approved": False}
    user_data[user_id]["bot_username"] = bot_name
    await update.message.reply_text(f"🤖 Bot tanlandi: {bot_name}\n/start orqali bosh menyuga qayting.")
    return ConversationHandler.END

# === CAPTCHA HANDLE ===
async def handle_captcha(client, bot_username):
    async for msg in client.iter_messages(bot_username, limit=10):
        if msg.message and 'нажми на кнопку' in msg.message:
            match = re.search(r'где изображено «(.+?)»', msg.message)
            if match:
                fruit = match.group(1).strip()
                emoji = emoji_map.get(fruit)
                if not emoji: return False
                if msg.buttons:
                    all_buttons = [btn for row in msg.buttons for btn in row]
                    random.shuffle(all_buttons)
                    for btn in all_buttons:
                        await asyncio.sleep(random.uniform(0.5, 1.2))
                        if emoji in btn.text:
                            await btn.click()
                            return True
    return False

# === AUTO CLICK LOOP ===
async def click_loop(user_id, client, bot_username):
    async with client:
        while True:
            try:
                await client.send_message(bot_username, '/start')
                await asyncio.sleep(random.uniform(2, 4))
                async for msg in client.iter_messages(bot_username, limit=10):
                    if msg.buttons:
                        for row in msg.buttons:
                            for btn in row:
                                if 'Кликер' in btn.text:
                                    await btn.click()
                                    await asyncio.sleep(2)
                                    solved = await handle_captcha(client, bot_username)
                                    await asyncio.sleep(360 if solved else 1200)
            except Exception as e:
                print(f"[{user_id}] Xatolik: {e}")
                await asyncio.sleep(10)

# === START CLICK ===
async def start_click(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    user_id = update.effective_user.id if not from_callback else update.callback_query.from_user.id
    chat = update.message if not from_callback else update.callback_query.message
    if not user_data[user_id]["approved"]:
        await chat.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return
    data = user_data.get(user_id)
    if not data or not data['accounts']:
        await chat.reply_text("❗ Avval akkaunt qo‘shing.")
        return
    if not data['bot_username']:
        await chat.reply_text("❗ Bot tanlanmagan. /add_bot orqali tanlang.")
        return
    if data['tasks']:
        await chat.reply_text("⚠️ Clicker allaqachon ishlayapti.")
        return
    for client in data['accounts']:
        task = asyncio.create_task(click_loop(user_id, client, data['bot_username']))
        data['tasks'].append(task)
    await chat.reply_text("▶️ Hamma akkauntlarda Clicker boshlandi.")

# === STOP CLICK ===
async def stop_click(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    user_id = update.effective_user.id if not from_callback else update.callback_query.from_user.id
    chat = update.message if not from_callback else update.callback_query.message
    if not user_data[user_id]["approved"]:
        await chat.reply_text("⛔ Sizda ruxsat yo'q. Iltimos, admin bilan bog'laning va pulni to'lang.")
        return
    data = user_data.get(user_id)
    if not data or not data['tasks']:
        await chat.reply_text("🚫 Clicker ishlamayapti.")
        return
    for task in data['tasks']:
        task.cancel()
    data['tasks'] = []
    await chat.reply_text("🛑 Clicker to‘xtatildi.")

# === RUN BOT AND FLASK ===
async def run_bot():
    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bot_name)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    await app.run_polling()

import threading
if __name__ == "__main__":
    bot_thread = threading.Thread(target=asyncio.run(run_bot()), daemon=True)
    bot_thread.start()

    # Flask serverni boshqa portda ishga tushirish
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

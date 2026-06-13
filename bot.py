import asyncio
import sqlite3
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '8746100227:AAGJEyqYREvDG45np8PbTBbySRJx3lJGizo'
CHANNEL_ID = -1001913679008
ADMINS = [8350819510, 6495811530]

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Веб-сервер для Render ---
async def handle(request):
    return web.Response(text="Bot is running!")

# --- Логика бота ---
class Reg(StatesGroup):
    fio = State()
    phone = State()
    mailing = State()

conn = sqlite3.connect('contest.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, phone TEXT)')
conn.commit()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="☎️ Support")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Участники", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_mailing")]
        ])
        await message.answer("👑 Админ-панель:", reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")],
            [InlineKeyboardButton(text="🎬 YouTube", url="https://www.youtube.com/@Azizzombistrim")],
            [InlineKeyboardButton(text="🎮 Kick", url="https://kick.com/aziz-zombi")],
            [InlineKeyboardButton(text="🟢 Tekshirish", callback_data="check_sub")]
        ])
        await message.answer("🎉 AZIZZOMBI KONKURS GA XUSH KELIBSIZ!\n\nObuna bo'lgandan keyin 🟢 Tekshirish tugmasini bosing.", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=call.from_user.id)
    if member.status in ['member', 'administrator', 'creator']:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 Ishtirok etish", callback_data="join_contest")]])
        await call.message.answer("✅ Ajoyib! Endi ishtirok etish tugmasini bosing.", reply_markup=kb)
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)

@dp.callback_query(F.data == "join_contest")
async def join(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите ваше ФИО:")
    await state.set_state(Reg.fio)

@dp.message(Reg.fio)
async def get_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Отправить номер", request_contact=True)]], resize_keyboard=True)
    await message.answer("✅ Qabul qilindi! Endi telefon raqamingizni yuboring:", reply_markup=kb)
    await state.set_state(Reg.phone)

@dp.message(Reg.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('INSERT OR REPLACE INTO users (id, name, phone) VALUES (?, ?, ?)', (message.from_user.id, data['fio'], message.contact.phone_number))
    conn.commit()
    await message.answer("🎉 Tabriklaymiz! Siz ro'yxatdan o'tdingiz.", reply_markup=main_menu())
    await state.clear()

@dp.message(F.text == "👤 Mening profilim")
async def profile(message: types.Message):
    cursor.execute('SELECT name, phone FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    text = (f"👋 Assalomu aleykum 👤 {user[0] if user else 'Mehmon'}\n"
            f"Profilingiz menyusiga xush kelibsiz\n\n"
            f"👤 Nick: @{message.from_user.username or 'Yo\'q'}\n"
            f"🆔 Botdagi ID: {message.from_user.id}\n"
            f"🆔 Telegram ID: {message.from_user.id}\n\n"
            f"☎️ Telefon: {user[1] if user else 'Kiritilmagan'}")
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✍️ Ismni o'zgartirish"), KeyboardButton(text="✍️ Kartalar sozlamasi")],
        [KeyboardButton(text="📞 Telefon raqamni o'zgartirish")],
        [KeyboardButton(text="🏠 Bosh saxifa")]
    ], resize_keyboard=True)
    await message.answer(text, reply_markup=kb)

@dp.message(F.text == "☎️ Support")
async def support(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Yozish", url="https://t.me/zombiadminuz")]
    ])
    text = ("Savol, shikoyat, takliflar bo'lsa bizga murojaat qilishingiz mumkin!\n\n"
            "adminga yozish 👇")
    await message.answer(text, reply_markup=kb)

@dp.message(F.text == "🏠 Bosh saxifa")
async def home(message: types.Message):
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    if call.data == "admin_stats":
        cursor.execute('SELECT count(*) FROM users')
        await call.message.answer(f"📊 Всего участников: {cursor.fetchone()[0]}")
    elif call.data == "admin_users":
        cursor.execute('SELECT name, phone FROM users')
        await call.message.answer("👥 Участники:\n" + "\n".join([f"{u[0]}: {u[1]}" for u in cursor.fetchall()]))
    elif call.data == "admin_mailing":
        await call.message.answer("Введите текст для рассылки:")
        await state.set_state(Reg.mailing)

@dp.message(Reg.mailing)
async def mailing_process(message: types.Message, state: FSMContext):
    cursor.execute('SELECT id FROM users')
    for row in cursor.fetchall():
        try: await bot.send_message(row[0], message.text)
        except: pass
    await message.answer("✅ Рассылка завершена!")
    await state.clear()

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
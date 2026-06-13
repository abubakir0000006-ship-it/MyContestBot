import asyncio
import sqlite3
import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8746100227:AAGJEyqYREvDG45np8PbTBbySRJx3lJGizo'
CHANNEL_ID = -1001913679008
ADMINS = [8350819510, 6495811530]

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Обновил таблицу: добавил колонку status (1 = участвует)
conn = sqlite3.connect('contest.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, status INTEGER)')
conn.commit()

class Reg(StatesGroup):
    fio = State()
    phone = State()
    mailing = State()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🎁 Konkursga qatnash")],
        [KeyboardButton(text="👨‍💻 Admin")]
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
            [InlineKeyboardButton(text="🟢 Tekshirish", callback_data="check_sub")]
        ])
        await message.answer("🎉 AZIZZOMBI KONKURS GA XUSH KELIBSIZ!\n\nObuna bo'lgandan keyin 🟢 Tekshirish tugmasini bosing.", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=call.from_user.id)
    if member.status in ['member', 'administrator', 'creator']:
        await call.message.answer("✅ Ajoyib! Endi asosiy menyudan '🎁 Konkursga qatnash' tugmasini bosing.", reply_markup=main_menu())
    else:
        await call.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)

@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_contest(message: types.Message, state: FSMContext):
    cursor.execute('SELECT status FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await message.answer("⚠️ Siz allaqachon ro'yxatdan o'tgansiz!")
    else:
        await message.answer("📝 Ishtirok etish uchun pasport bo'yicha FIO kiriting:")
        await state.set_state(Reg.fio)

@dp.message(Reg.fio)
async def get_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)]], resize_keyboard=True)
    await message.answer("✅ Qabul qilindi! Endi telefon raqamingizni yuboring:", reply_markup=kb)
    await state.set_state(Reg.phone)

@dp.message(Reg.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('INSERT OR REPLACE INTO users (id, name, phone, status) VALUES (?, ?, ?, 1)', 
                   (message.from_user.id, data['fio'], message.contact.phone_number))
    conn.commit()
    await message.answer("🎉 Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz.", reply_markup=main_menu())
    await state.clear()

@dp.message(F.text == "👤 Mening profilim")
async def profile(message: types.Message):
    cursor.execute('SELECT name, phone FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    text = (f"👋 Assalomu aleykum 👤 {user[0] if user else 'Mehmon'}\n"
            f"Profilingiz ma'lumotlari:\n\n"
            f"👤 Nick: @{message.from_user.username or 'Yo\'q'}\n"
            f"🆔 Botdagi ID: {message.from_user.id}\n\n"
            f"☎️ Telefon: {user[1] if user else 'Kiritilmagan'}")
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✍️ Ismni o'zgartirish"), KeyboardButton(text="📞 Telefon raqamni o'zgartirish")],
        [KeyboardButton(text="🏠 Bosh saxifa")]
    ], resize_keyboard=True)
    await message.answer(text, reply_markup=kb)

@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: types.Message):
    await message.answer("✍️ Savollaringiz bo'lsa adminga yozing: https://t.me/zombiadminuz")

@dp.message(F.text == "🏠 Bosh saxifa")
async def home(message: types.Message):
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu())

@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    if call.data == "admin_stats":
        cursor.execute('SELECT count(*) FROM users')
        await call.message.answer(f"📊 Jami ishtirokchilar: {cursor.fetchone()[0]}")
    elif call.data == "admin_users":
        cursor.execute('SELECT name, phone FROM users')
        await call.message.answer("👥 Ishtirokchilar:\n" + "\n".join([f"{u[0]}: {u[1]}" for u in cursor.fetchall()]))
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

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_web_server()
    print("Bot is starting...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
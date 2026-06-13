import asyncio
import sqlite3
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# Настройки
API_TOKEN = '8746100227:AAGJEyqYREvDG45np8PbTBbySRJx3lJGizo'
CHANNEL_ID = -1001913679008
ADMINS = [8350819510, 6495811530]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# База данных
conn = sqlite3.connect('contest.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, registered INTEGER DEFAULT 0)')
conn.commit()

class Reg(StatesGroup):
    fio = State()
    phone = State()
    mailing_text = State()
    mailing_photo = State()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🎁 Konkursga qatnash")],
        [KeyboardButton(text="👨‍💻 Admin")]
    ], resize_keyboard=True)

# Обработка команд
@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMINS:
        await message.answer("👑 Admin-panel faol.")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Tekshirish", callback_data="check_sub")]
        ])
        await message.answer("🎉 Konkursga xush kelibsiz! Obuna bo'ling va tugmani bosing.", reply_markup=kb)

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    await call.message.answer("✅ Ajoyib! Asosiy menyudan '🎁 Konkursga qatnash' tugmasini bosing.", reply_markup=main_menu())

@dp.callback_query(F.data == "join_contest")
@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_contest(event: types.Message | types.CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    cursor.execute('SELECT registered FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user and user[0] == 1:
        text = "⚠️ Siz allaqachon ro'yxatdan o'tgansiz!"
        if isinstance(event, types.CallbackQuery): await event.answer(text, show_alert=True)
        else: await event.answer(text)
    else:
        await (event.message if isinstance(event, types.CallbackQuery) else event).answer("📝 FIO kiriting:")
        await state.set_state(Reg.fio)

@dp.message(Reg.fio)
async def get_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)]], resize_keyboard=True)
    await message.answer("✅ Telefon raqamingizni yuboring:", reply_markup=kb)
    await state.set_state(Reg.phone)

@dp.message(Reg.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('INSERT OR REPLACE INTO users (id, name, phone, registered) VALUES (?, ?, ?, 1)', (message.from_user.id, data['fio'], message.contact.phone_number))
    conn.commit()
    await message.answer("🎉 Tabriklaymiz! Siz ro'yxatdan o'tdingiz.", reply_markup=main_menu())
    await state.clear()

# ВЕБ-СЕРВЕР ДЛЯ RENDER
async def web_handler(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', web_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 8080)))
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

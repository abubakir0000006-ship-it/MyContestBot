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

@dp.message(Command("start"))
async def start(message: types.Message):
    if message.from_user.id in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Участники", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Рассылка конкурса", callback_data="admin_mailing")]
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
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=call.from_user.id)
        if member.status in ['member', 'administrator', 'creator']:
            await call.message.answer("✅ Ajoyib! Endi asosiy menyudan '🎁 Konkursga qatnash' tugmasini bosing.", reply_markup=main_menu())
        else:
            await call.message.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")]]))
    except:
        await call.answer("❌ Xatolik!")

@dp.callback_query(F.data == "join_contest")
async def join_contest_callback(call: types.CallbackQuery, state: FSMContext):
    cursor.execute('SELECT registered FROM users WHERE id = ?', (call.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await call.answer("⚠️ Siz allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
        await call.message.answer("⚠️ Siz allaqachon konkursda qatnashyapsiz, qayta ro'yxatdan o'tish imkonsiz!")
    else:
        await call.message.answer("📝 Ishtirok etish uchun pasport bo'yicha FIO kiriting:")
        await state.set_state(Reg.fio)

@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_contest(message: types.Message, state: FSMContext):
    cursor.execute('SELECT registered FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await message.answer("⚠️ Siz allaqachon ro'yxatdan o'tgansiz va konkursda qatnashyapsiz!")
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
    cursor.execute('INSERT OR REPLACE INTO users (id, name, phone, registered) VALUES (?, ?, ?, 1)', (message.from_user.id, data['fio'], message.contact.phone_number))
    conn.commit()
    await message.answer("🎉 Tabriklaymiz! Siz qabul qilindingiz va konkursda ishtirok etyapsiz.", reply_markup=main_menu())
    await state.clear()

@dp.message(F.text == "👤 Mening profilim")
async def profile(message: types.Message):
    cursor.execute('SELECT name, phone FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    text = (f"👋 Assalomu aleykum 👤 {user[0] if user else 'Mehmon'}\n"
            f"👤 Nick: @{message.from_user.username or 'Yo\'q'}\n"
            f"🆔 ID: {message.from_user.id}\n\n"
            f"☎️ Telefon: {user[1] if user else 'Kiritilmagan'}")
    await message.answer(text, reply_markup=main_menu())

@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: types.Message):
    await message.answer("✍️ Savollaringiz bo'lsa adminga yozing: https://t.me/zombiadminuz")

@dp.callback_query(F.data == "admin_stats")
async def stats(call: types.CallbackQuery):
    cursor.execute('SELECT count(*) FROM users')
    await call.message.answer(f"📊 Всего участников: {cursor.fetchone()[0]}")

@dp.callback_query(F.data == "admin_users")
async def users_list(call: types.CallbackQuery):
    cursor.execute('SELECT name, phone FROM users WHERE registered = 1')
    users = cursor.fetchall()
    text = "👥 Участники:\n" + "\n".join([f"{u[0]}: {u[1]}" for u in users])
    await call.message.answer(text[:4000] if text else "Нет участников")

@dp.callback_query(F.data == "admin_mailing")
async def mailing_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Пришлите фото для конкурса:")
    await state.set_state(Reg.mailing_photo)

@dp.message(Reg.mailing_photo, F.photo)
async def get_mailing_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Теперь пришлите описание конкурса:")
    await state.set_state(Reg.mailing_text)

@dp.message(Reg.mailing_text)
async def get_mailing_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('SELECT id FROM users')
    users = cursor.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Принять участие", callback_data="join_contest")]])
    for u in users:
        try: await bot.send_photo(u[0], data['photo'], caption=message.text, reply_markup=kb)
        except: pass
    await message.answer("✅ Рассылка отправлена!")
    await state.clear()

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000)))
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
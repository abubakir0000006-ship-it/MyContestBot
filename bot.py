import asyncio
import sqlite3
import os
import logging
import random
import csv
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile

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
    random_count = State()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🎁 Konkursga qatnash")],
        [KeyboardButton(text="👨‍💻 Admin")]
    ], resize_keyboard=True)

# --- АВТО-НАПОМИНАЛКА ---
async def auto_reminder():
    while True:
        await asyncio.sleep(3600)  # Проверка каждый час
        cursor.execute('SELECT id FROM users WHERE registered = 0')
        unregistered_users = cursor.fetchall()
        for u in unregistered_users:
            try:
                await bot.send_message(u[0], "👋 Salom! Konkursda hali qatnashmadingiz. Tezroq ro'yxatdan o'ting va yutuqlarni yutib oling! 🎁")
            except: pass

@dp.message(Command("start"))
async def start(message: types.Message):
    cursor.execute('INSERT OR IGNORE INTO users (id) VALUES (?)', (message.from_user.id,))
    conn.commit()
    if message.from_user.id in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📥 Bazani yuklab olish", callback_data="admin_export")],
            [InlineKeyboardButton(text="📢 Konkurs rasilkasi", callback_data="admin_mailing")],
            [InlineKeyboardButton(text="🎲 Random", callback_data="admin_random")]
        ])
        await message.answer("👑 Admin-panel:", reply_markup=kb)
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
            await call.answer("❌ Siz hali kanalga obuna bo'lmagansiz!", show_alert=True)
    except: await call.answer("❌ Xatolik yuz berdi!")

@dp.callback_query(F.data == "admin_export")
async def admin_export(call: types.CallbackQuery):
    cursor.execute('SELECT id, name, phone FROM users WHERE registered = 1')
    rows = cursor.fetchall()
    file_name = "users.csv"
    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "FIO", "Phone"])
        writer.writerows(rows)
    await call.message.answer_document(FSInputFile(file_name))
    os.remove(file_name)

@dp.callback_query(F.data == "admin_random")
async def admin_random_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите количество победителей (от 1 до 20):")
    await state.set_state(Reg.random_count)

@dp.message(Reg.random_count)
async def process_random(message: types.Message, state: FSMContext):
    try:
        count = int(message.text)
        cursor.execute('SELECT name, phone FROM users WHERE registered = 1')
        users = cursor.fetchall()
        if not users: await message.answer("Ishtirokchilar hali yo'q!")
        else:
            winners = random.sample(users, min(count, len(users)))
            res = "🎁 G'oliblar:\n" + "\n".join([f"{w[0]} ({w[1]})" for w in winners])
            await message.answer(res)
        await state.clear()
    except: await message.answer("Xatolik! Iltimos, raqam kiriting.")

@dp.callback_query(F.data == "join_contest")
async def join_contest_callback(call: types.CallbackQuery, state: FSMContext):
    cursor.execute('SELECT registered FROM users WHERE id = ?', (call.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1: await call.answer("⚠️ Siz allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
    else:
        await call.message.answer("📝 Ishtirok etish uchun pasport bo'yicha FIO kiriting:")
        await state.set_state(Reg.fio)

@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_contest(message: types.Message, state: FSMContext):
    cursor.execute('SELECT registered FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1: await message.answer("⚠️ Siz allaqachon konkursda qatnashyapsiz!")
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
    cursor.execute('UPDATE users SET name=?, phone=?, registered=1 WHERE id=?', (data['fio'], message.contact.phone_number, message.from_user.id))
    conn.commit()
    await message.answer("🎉 Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz.", reply_markup=main_menu())
    await state.clear()

@dp.message(F.text == "👤 Mening profilim")
async def profile(message: types.Message):
    cursor.execute('SELECT name, phone FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    text = (f"👋 Assalomu aleykum 👤 {user[0] if user and user[0] else 'Mehmon'}\n"
            f"🆔 ID: {message.from_user.id}\n\n"
            f"☎️ Telefon: {user[1] if user and user[1] else 'Kiritilmagan'}")
    await message.answer(text, reply_markup=main_menu())

@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: types.Message):
    await message.answer("✍️ Savollaringiz bo'lsa adminga yozing: https://t.me/zombiadminuz")

@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    if call.data == "admin_stats":
        cursor.execute('SELECT count(*) FROM users WHERE registered = 1')
        await call.message.answer(f"📊 Jami ishtirokchilar: {cursor.fetchone()[0]}")
    elif call.data == "admin_users":
        cursor.execute('SELECT name, phone FROM users WHERE registered = 1')
        users = cursor.fetchall()
        text = "👥 Ishtirokchilar:\n" + "\n".join([f"{u[0]}: {u[1]}" for u in users])
        await call.message.answer(text[:4000] if text else "Ishtirokchilar yo'q")
    elif call.data == "admin_mailing":
        await call.message.answer("Rasm yuboring:")
        await state.set_state(Reg.mailing_photo)

@dp.message(Reg.mailing_photo, F.photo)
async def get_mailing_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Konkurs tavsifini yozing:")
    await state.set_state(Reg.mailing_text)

@dp.message(Reg.mailing_text)
async def get_mailing_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('SELECT id FROM users')
    users = cursor.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")],
        [InlineKeyboardButton(text="🎬 YouTube", url="https://www.youtube.com/@Azizzombistrim")],
        [InlineKeyboardButton(text="🎮 Kick", url="https://kick.com/aziz-zombi")],
        [InlineKeyboardButton(text="✅ Ishtirok etish", callback_data="join_contest")]
    ])
    for u in users:
        try: await bot.send_photo(u[0], data['photo'], caption=message.text, reply_markup=kb)
        except: pass
    await message.answer("✅ Rasylka yuborildi!")
    await state.clear()

async def handle(request): return web.Response(text="Bot is running")
async def run_web():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 8080)))
    await site.start()

async def main():
    await run_web()
    asyncio.create_task(auto_reminder()) # Запускаем напоминалку
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

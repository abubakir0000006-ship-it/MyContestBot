import asyncio
import sqlite3
import os
import logging
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8746100227:AAGJEyqYREvDG45np8PbTBbySRJx3lJGizo'
ADMINS = [8350819510, 6495811530]
# Впиши сюда юзернеймы каналов БЕЗ @ (пример: "kanal1", "kanal2")
CHANNELS = ["kanal1", "kanal2", "kanal3"]

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

async def check_subs(user_id):
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except: return False
    return True

@dp.message(Command("start"))
async def start(message: types.Message):
    cursor.execute('INSERT OR IGNORE INTO users (id) VALUES (?)', (message.from_user.id,))
    conn.commit()
    if message.from_user.id in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🎲 Random", callback_data="admin_random")],
            [InlineKeyboardButton(text="📢 Rasilka", callback_data="admin_mailing")]
        ])
        await message.answer("👑 Admin-panel:", reply_markup=kb)
    else:
        await message.answer("🎉 Konkursga xush kelibsiz! Avval 3 ta kanalga obuna bo'ling va keyin '🟢 Tekshirish' tugmasini bosing.",
                           reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🟢 Tekshirish", callback_data="check_sub")]]))

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    if await check_subs(call.from_user.id):
        await call.message.answer("✅ Ajoyib! Endi asosiy menyudan '🎁 Konkursga qatnash' tugmasini bosing.", reply_markup=main_menu())
    else:
        await call.answer("❌ Siz barcha kanallarga obuna bo'lmagansiz!", show_alert=True)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: types.CallbackQuery):
    cursor.execute('SELECT count(*) FROM users')
    all_users = cursor.fetchone()[0]
    cursor.execute('SELECT count(*) FROM users WHERE registered = 1')
    reg_users = cursor.fetchone()[0]
    await call.message.answer(f"📊 Statistika:\n\n👥 Jami foydalanuvchilar: {all_users}\n🎯 Konkurs ishtirokchilari: {reg_users}")

@dp.callback_query(F.data == "admin_random")
async def admin_random(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Введите количество победителей (1-20):")
    await state.set_state(Reg.random_count)

@dp.message(Reg.random_count)
async def process_random(message: types.Message, state: FSMContext):
    try:
        count = int(message.text)
        cursor.execute('SELECT name, phone FROM users WHERE registered = 1')
        users = cursor.fetchall()
        winners = random.sample(users, min(count, len(users)))
        res = "🎁 G'oliblar:\n" + "\n".join([f"{w[0]} ({w[1]})" for w in winners])
        await message.answer(res)
        await state.clear()
    except: await message.answer("Xatolik! Raqam kiriting.")

@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_reg(message: types.Message, state: FSMContext):
    await message.answer("📝 Ishtirok etish uchun FIO kiriting:")
    await state.set_state(Reg.fio)

@dp.message(Reg.fio)
async def get_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    await message.answer("📞 Raqamni yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Yuborish", request_contact=True)]], resize_keyboard=True))
    await state.set_state(Reg.phone)

@dp.message(Reg.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('UPDATE users SET name=?, phone=?, registered=1 WHERE id=?', (data['fio'], message.contact.phone_number, message.from_user.id))
    conn.commit()
    await message.answer("🎉 Muvaffaqiyatli!", reply_markup=main_menu())
    await state.clear()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

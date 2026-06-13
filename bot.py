import asyncio
import sqlite3
import logging
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
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📢 Konkurs rasilkasi", callback_data="admin_mailing")]
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
    except:
        await call.answer("❌ Xatolik!")

@dp.callback_query(F.data == "join_contest")
async def join_contest_callback(call: types.CallbackQuery, state: FSMContext):
    cursor.execute('SELECT registered FROM users WHERE id = ?', (call.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await call.answer("⚠️ Siz allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
    else:
        await call.message.answer("📝 Ishtirok etish uchun pasport bo'yicha FIO kiriting:")
        await state.set_state(Reg.fio)

@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_contest(message: types.Message, state: FSMContext):
    cursor.execute('SELECT registered FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await message.answer("⚠️ Siz allaqachon konkursda qatnashyapsiz!")
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
    cursor.execute('INSERT OR REPLACE INTO users (id, name, phone, registered) VALUES (?, ?, ?, 1)', 
                   (message.from_user.id, data['fio'], message.contact.phone_number))
    conn.commit()
    await message.answer("🎉 Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz.", reply_markup=main_menu())
    await state.clear()

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

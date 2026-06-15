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

# ============================================================
# НОВЫЕ КОЛОНКИ (добавляем если нет)
# ============================================================
try:
    cursor.execute('ALTER TABLE users ADD COLUMN blocked INTEGER DEFAULT 0')
    conn.commit()
except: pass
try:
    cursor.execute('ALTER TABLE users ADD COLUMN ticket TEXT')
    conn.commit()
except: pass
try:
    cursor.execute('ALTER TABLE users ADD COLUMN ref_by INTEGER DEFAULT 0')
    conn.commit()
except: pass

# Таблица для истории рассылок
cursor.execute('''CREATE TABLE IF NOT EXISTS mailings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    date TEXT
)''')
conn.commit()

# ============================================================
# СТАРЫЕ СОСТОЯНИЯ (не трогаем)
# ============================================================
class Reg(StatesGroup):
    fio = State()
    phone = State()
    mailing_text = State()
    mailing_photo = State()
    random_count = State()

# ============================================================
# НОВЫЕ СОСТОЯНИЯ
# ============================================================
class AdminNew(StatesGroup):
    search_query = State()
    add_admin_id = State()
    contest_date = State()
    edit_fio = State()
    edit_phone = State()

class UserNew(StatesGroup):
    edit_fio = State()
    edit_phone = State()

# ============================================================
# СТАРЫЕ ФУНКЦИИ (не трогаем)
# ============================================================
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🎁 Konkursga qatnash")],
        [KeyboardButton(text="👨‍💻 Admin")]
    ], resize_keyboard=True)

async def auto_reminder():
    while True:
        await asyncio.sleep(10800)
        cursor.execute('SELECT id FROM users WHERE registered = 0')
        unregistered_users = cursor.fetchall()
        for u in unregistered_users:
            if u[0] not in ADMINS:
                try:
                    await bot.send_message(u[0], "👋 Salom! Konkursda hali qatnashmadingiz. Tezroq ro'yxatdan o'ting va yutuqlarni yutib oling! 🎁")
                except: pass

@dp.message(Command("start"))
async def start(message: types.Message):
    # Реферальная ссылка
    args = message.text.split()
    ref_id = int(args[1].replace('ref_', '')) if len(args) > 1 and args[1].startswith('ref_') else 0

    cursor.execute('INSERT OR IGNORE INTO users (id, ref_by) VALUES (?, ?)', (message.from_user.id, ref_id))
    conn.commit()

    if message.from_user.id in ADMINS:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Kanal obunachilari", callback_data="admin_chan_stats")],
            [InlineKeyboardButton(text="🤖 Botdagi obunachilar soni", callback_data="admin_bot_users")],
            [InlineKeyboardButton(text="👥 Ishtirokchilar", callback_data="admin_users")],
            [InlineKeyboardButton(text="📥 Bazani yuklab olish", callback_data="admin_export")],
            [InlineKeyboardButton(text="📢 Konkurs rasilkasi", callback_data="admin_mailing")],
            [InlineKeyboardButton(text="🎲 Random", callback_data="admin_random")],
            # НОВЫЕ кнопки для админа
            [InlineKeyboardButton(text="🔍 Ishtirokchi qidirish", callback_data="admin_search")],
            [InlineKeyboardButton(text="📋 Bloklangan foydalanuvchilar", callback_data="admin_blocked")],
            [InlineKeyboardButton(text="📜 Rasylka tarixi", callback_data="admin_mailing_history")],
            [InlineKeyboardButton(text="📅 Konkurs sanasini belgilash", callback_data="admin_set_date")],
            [InlineKeyboardButton(text="👑 Admin qo'shish", callback_data="admin_add_admin")],
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
    # Генерируем уникальный номер билета
    ticket = f"AZ-{random.randint(10000, 99999)}"
    cursor.execute('UPDATE users SET name=?, phone=?, registered=1, ticket=? WHERE id=?',
                   (data['fio'], message.contact.phone_number, ticket, message.from_user.id))
    conn.commit()
    await message.answer(
        f"🎉 Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz.\n\n"
        f"🎫 Sizning bilet raqamingiz: <b>{ticket}</b>\n\n"
        f"Natijalarni kuting! Omad! 🍀",
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await state.clear()

@dp.message(F.text == "👤 Mening profilim")
async def profile(message: types.Message):
    cursor.execute('SELECT name, phone, ticket, registered FROM users WHERE id = ?', (message.from_user.id,))
    user = cursor.fetchone()

    # Реферальная ссылка
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"

    # Считаем рефералов
    cursor.execute('SELECT count(*) FROM users WHERE ref_by = ?', (message.from_user.id,))
    ref_count = cursor.fetchone()[0]

    status = "✅ Ro'yxatdan o'tgan" if user and user[3] == 1 else "⏳ Ro'yxatdan o'tmagan"
    ticket_text = f"\n🎫 Bilet: <b>{user[2]}</b>" if user and user[2] else ""

    text = (
        f"👋 Assalomu aleykum 👤 {user[0] if user and user[0] else 'Mehmon'}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"☎️ Telefon: {user[1] if user and user[1] else 'Kiritilmagan'}\n"
        f"📊 Status: {status}"
        f"{ticket_text}\n\n"
        f"👥 Referal: {ref_count} ta do'st taklif qildingiz\n"
        f"🔗 Sizning havolangiz:\n{ref_link}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ma'lumotlarni tahrirlash", callback_data="user_edit")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: types.Message):
    await message.answer("✍️ Savollaringiz bo'lsa adminga yozing: https://t.me/zombiadminuz")

@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    if call.data == "admin_stats":
        cursor.execute('SELECT count(*) FROM users WHERE registered = 1')
        reg = cursor.fetchone()[0]
        cursor.execute('SELECT count(*) FROM users WHERE blocked = 1')
        blocked = cursor.fetchone()[0]
        cursor.execute('SELECT count(*) FROM users WHERE ref_by != 0')
        refs = cursor.fetchone()[0]
        await call.message.answer(
            f"📊 Statistika:\n"
            f"✅ Jami ishtirokchilar: {reg}\n"
            f"🚫 Bloklangan: {blocked}\n"
            f"🔗 Referal orqali kelgan: {refs}"
        )

    elif call.data == "admin_chan_stats":
        try:
            count = await bot.get_chat_member_count(CHANNEL_ID)
            await call.message.answer(f"📢 Kanalda jami: {count} ta obunachi bor.")
        except: await call.answer("Xatolik! Bot kanal admini emas.")

    elif call.data == "admin_bot_users":
        cursor.execute('SELECT count(*) FROM users')
        await call.message.answer(f"🤖 Botdagi jami obunachilar soni: {cursor.fetchone()[0]}")

    elif call.data == "admin_users":
        cursor.execute('SELECT name, phone, ticket FROM users WHERE registered = 1')
        users = cursor.fetchall()
        text = "👥 Ishtirokchilar:\n" + "\n".join([f"{u[0]}: {u[1]} | 🎫{u[2] or '-'}" for u in users])
        await call.message.answer(text[:4000] if text else "Ishtirokchilar yo'q")

    elif call.data == "admin_mailing":
        await call.message.answer("Rasm yuboring:")
        await state.set_state(Reg.mailing_photo)

    # ============================================================
    # НОВЫЕ ОБРАБОТЧИКИ АДМИНА
    # ============================================================
    elif call.data == "admin_search":
        await call.message.answer("🔍 Ism yoki telefon raqam kiriting:")
        await state.set_state(AdminNew.search_query)

    elif call.data == "admin_blocked":
        cursor.execute('SELECT id, name, phone FROM users WHERE blocked = 1')
        users = cursor.fetchall()
        if not users:
            await call.message.answer("🚫 Bloklangan foydalanuvchilar yo'q.")
        else:
            text = "🚫 Bloklangan:\n"
            for u in users:
                text += f"\nID: {u[0]} | {u[1]} | {u[2]}"
            await call.message.answer(text[:4000])

    elif call.data == "admin_mailing_history":
        cursor.execute('SELECT id, text, date FROM mailings ORDER BY id DESC LIMIT 10')
        rows = cursor.fetchall()
        if not rows:
            await call.message.answer("📜 Rasylka tarixi yo'q.")
        else:
            text = "📜 So'nggi rasylkalar:\n\n"
            for r in rows:
                text += f"#{r[0]} | {r[2]}\n{r[1][:80]}...\n\n"
            await call.message.answer(text[:4000])

    elif call.data == "admin_set_date":
        await call.message.answer("📅 Konkurs sanasini kiriting (masalan: 25.01.2025 20:00):")
        await state.set_state(AdminNew.contest_date)

    elif call.data == "admin_add_admin":
        await call.message.answer("👑 Yangi admin Telegram ID sini kiriting:")
        await state.set_state(AdminNew.add_admin_id)

    elif call.data.startswith("admin_block_"):
        uid = int(call.data.split("_")[2])
        cursor.execute('UPDATE users SET blocked=1 WHERE id=?', (uid,))
        conn.commit()
        try:
            await bot.send_message(uid, "🚫 Siz konkursdan bloklangansiz. Savollar uchun: https://t.me/zombiadminuz")
        except: pass
        await call.message.answer(f"✅ Foydalanuvchi {uid} bloklandi.")

    elif call.data.startswith("admin_unblock_"):
        uid = int(call.data.split("_")[2])
        cursor.execute('UPDATE users SET blocked=0 WHERE id=?', (uid,))
        conn.commit()
        try:
            await bot.send_message(uid, "✅ Sizning blokirovkangiz olib tashlandi! Konkursda qatnashishingiz mumkin.")
        except: pass
        await call.message.answer(f"✅ Foydalanuvchi {uid} blokdan chiqarildi.")

    elif call.data.startswith("admin_delete_"):
        uid = int(call.data.split("_")[2])
        cursor.execute('DELETE FROM users WHERE id=?', (uid,))
        conn.commit()
        await call.message.answer(f"🗑 Foydalanuvchi {uid} bazadan o'chirildi.")

# ============================================================
# НОВЫЕ STATE ОБРАБОТЧИКИ — АДМИН
# ============================================================

@dp.message(AdminNew.search_query)
async def admin_search_result(message: types.Message, state: FSMContext):
    query = message.text.strip()
    cursor.execute(
        'SELECT id, name, phone, registered, blocked, ticket FROM users WHERE name LIKE ? OR phone LIKE ?',
        (f'%{query}%', f'%{query}%')
    )
    users = cursor.fetchall()
    await state.clear()
    if not users:
        await message.answer("❌ Topilmadi.")
        return
    for u in users:
        status = "✅ Ro'yxatdan o'tgan" if u[3] == 1 else "⏳ O'tmagan"
        blocked = "🚫 Bloklangan" if u[4] == 1 else "✔️ Faol"
        text = (
            f"👤 {u[1] or 'Noma\\'lum'}\n"
            f"🆔 ID: {u[0]}\n"
            f"☎️ {u[2] or '-'}\n"
            f"🎫 Bilet: {u[5] or '-'}\n"
            f"📊 {status} | {blocked}"
        )
        block_btn = "✅ Blokdan chiqarish" if u[4] == 1 else "🚫 Bloklash"
        block_cb = f"admin_unblock_{u[0]}" if u[4] == 1 else f"admin_block_{u[0]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=block_btn, callback_data=block_cb)],
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_delete_{u[0]}")]
        ])
        await message.answer(text, reply_markup=kb)

@dp.message(AdminNew.add_admin_id)
async def admin_add_admin(message: types.Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id not in ADMINS:
            ADMINS.append(new_admin_id)
            cursor.execute('INSERT OR IGNORE INTO users (id) VALUES (?)', (new_admin_id,))
            conn.commit()
            await message.answer(f"✅ {new_admin_id} admin sifatida qo'shildi!\n⚠️ Eslatma: Bot qayta ishga tushirilganda bu o'zgarish saqlanmaydi. Doimiy qilish uchun ADMINS ro'yxatiga qo'shing.")
            try:
                await bot.send_message(new_admin_id, "👑 Siz admin sifatida qo'shildingiz! /start buyrug'ini bosing.")
            except: pass
        else:
            await message.answer("⚠️ Bu foydalanuvchi allaqachon admin.")
    except:
        await message.answer("❌ Xatolik! Faqat raqam kiriting.")
    await state.clear()

@dp.message(AdminNew.contest_date)
async def admin_set_date(message: types.Message, state: FSMContext):
    date_text = message.text.strip()
    cursor.execute('SELECT id FROM users WHERE registered = 1')
    users = cursor.fetchall()
    count = 0
    for u in users:
        try:
            await bot.send_message(
                u[0],
                f"📅 E'lon!\n\nKonkurs sana va vaqti belgilandi:\n🗓 <b>{date_text}</b>\n\nOmad tilaymiz! 🍀",
                parse_mode="HTML"
            )
            count += 1
        except: pass
    await message.answer(f"✅ Konkurs sanasi {count} ta ishtirokchiga yuborildi: {date_text}")
    await state.clear()

# ============================================================
# НОВЫЕ ОБРАБОТЧИКИ — ЮЗЕР (редактирование данных)
# ============================================================

@dp.callback_query(F.data == "user_edit")
async def user_edit_menu(call: types.CallbackQuery):
    cursor.execute('SELECT registered FROM users WHERE id=?', (call.from_user.id,))
    user = cursor.fetchone()
    if not user or user[0] == 0:
        await call.answer("❌ Avval ro'yxatdan o'ting!", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ FIO ni o'zgartirish", callback_data="user_edit_fio")],
        [InlineKeyboardButton(text="📞 Telefon raqamni o'zgartirish", callback_data="user_edit_phone")]
    ])
    await call.message.answer("Nimani o'zgartirmoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data == "user_edit_fio")
async def user_edit_fio_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("✏️ Yangi FIO ni kiriting (pasport bo'yicha):")
    await state.set_state(UserNew.edit_fio)

@dp.message(UserNew.edit_fio)
async def user_edit_fio_finish(message: types.Message, state: FSMContext):
    cursor.execute('UPDATE users SET name=? WHERE id=?', (message.text.strip(), message.from_user.id))
    conn.commit()
    await message.answer("✅ FIO muvaffaqiyatli yangilandi!", reply_markup=main_menu())
    await state.clear()

@dp.callback_query(F.data == "user_edit_phone")
async def user_edit_phone_start(call: types.CallbackQuery, state: FSMContext):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)]], resize_keyboard=True)
    await call.message.answer("📞 Yangi telefon raqamingizni yuboring:", reply_markup=kb)
    await state.set_state(UserNew.edit_phone)

@dp.message(UserNew.edit_phone, F.contact)
async def user_edit_phone_finish(message: types.Message, state: FSMContext):
    cursor.execute('UPDATE users SET phone=? WHERE id=?', (message.contact.phone_number, message.from_user.id))
    conn.commit()
    await message.answer("✅ Telefon raqam muvaffaqiyatli yangilandi!", reply_markup=main_menu())
    await state.clear()

# ============================================================
# НОВАЯ КНОПКА — Поделиться ботом
# ============================================================

@dp.message(F.text == "🔗 Do'stlarga ulashish")
async def share_bot(message: types.Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    cursor.execute('SELECT count(*) FROM users WHERE ref_by=?', (message.from_user.id,))
    count = cursor.fetchone()[0]
    await message.answer(
        f"🔗 Do'stlaringizni taklif qiling!\n\n"
        f"Sizning havolangiz:\n{ref_link}\n\n"
        f"👥 Siz taklif qilgan do'stlar: {count} ta",
        reply_markup=main_menu()
    )

# ============================================================
# СТАРЫЙ ОБРАБОТЧИК РАССЫЛКИ (немного расширен — сохраняем в историю)
# ============================================================

@dp.message(Reg.mailing_photo, F.photo)
async def get_mailing_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Konkurs tavsifini yozing:")
    await state.set_state(Reg.mailing_text)

@dp.message(Reg.mailing_text)
async def get_mailing_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('SELECT id FROM users WHERE blocked = 0')
    users = cursor.fetchall()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")],
        [InlineKeyboardButton(text="🎬 YouTube", url="https://www.youtube.com/@Azizzombistrim")],
        [InlineKeyboardButton(text="🎮 Kick", url="https://kick.com/aziz-zombi")],
        [InlineKeyboardButton(text="✅ Ishtirok etish", callback_data="join_contest")]
    ])
    sent = 0
    for u in users:
        try:
            await bot.send_photo(u[0], data['photo'], caption=message.text, reply_markup=kb)
            sent += 1
        except: pass

    # Сохраняем в историю рассылок
    from datetime import datetime
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    cursor.execute('INSERT INTO mailings (text, date) VALUES (?, ?)', (message.text, now))
    conn.commit()

    await message.answer(f"✅ Rasylka yuborildi! {sent} ta foydalanuvchiga yetdi.")
    await state.clear()

# ============================================================
# ВЕБ + ЗАПУСК
# ============================================================

async def run_web():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 8080)))
    await site.start()

async def main():
    await run_web()
    asyncio.create_task(auto_reminder())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

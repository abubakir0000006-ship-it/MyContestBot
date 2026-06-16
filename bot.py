import asyncio
import sqlite3
import os
import logging
import random
import csv
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8746100227:AAGJEyqYREvDG45np8PbTBbySRJx3lJGizo'
CHANNEL_ID = -1001913679008
ADMINS = [8350819510, 6495811530]

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ─── DATABASE ─────────────────────────────────────────────────────────────────
conn = sqlite3.connect('contest.db', check_same_thread=False)
cursor = conn.cursor()

cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY,
        name        TEXT,
        phone       TEXT,
        registered  INTEGER DEFAULT 0,
        joined_at   TEXT
    );
    CREATE TABLE IF NOT EXISTS broadcast_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sent_count  INTEGER,
        fail_count  INTEGER,
        sent_at     TEXT
    );
""")
conn.commit()


# ─── STATES ───────────────────────────────────────────────────────────────────
class Reg(StatesGroup):
    fio           = State()
    phone         = State()
    mailing_text  = State()
    mailing_photo = State()
    random_count  = State()
    ban_id        = State()
    broadcast_confirm = State()


# ─── KEYBOARDS ────────────────────────────────────────────────────────────────
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🎁 Konkursga qatnash")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="👨‍💻 Admin")]
    ], resize_keyboard=True)


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika",        callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Kanal stat",        callback_data="admin_chan_stats"),
        ],
        [
            InlineKeyboardButton(text="🤖 Bot foydalanuvchilari", callback_data="admin_bot_users"),
            InlineKeyboardButton(text="👥 Ishtirokchilar",    callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="📥 CSV yuklab olish",  callback_data="admin_export"),
            InlineKeyboardButton(text="📋 Broadcast tarixi",  callback_data="admin_bcast_log"),
        ],
        [
            InlineKeyboardButton(text="📢 Xabar yuborish",    callback_data="admin_mailing"),
            InlineKeyboardButton(text="🎲 G'olib aniqlash",   callback_data="admin_random"),
        ],
        [
            InlineKeyboardButton(text="🔄 Konkursni yangilash", callback_data="admin_reset_contest"),
            InlineKeyboardButton(text="🚫 Foydalanuvchini bloklash", callback_data="admin_ban"),
        ],
    ])


def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")],
        [InlineKeyboardButton(text="🎬 YouTube",  url="https://www.youtube.com/@Azizzombistrim")],
        [InlineKeyboardButton(text="🎮 Kick",     url="https://kick.com/aziz-zombi")],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
    ])


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def is_admin(uid: int) -> bool:
    return uid in ADMINS


async def get_full_stats() -> str:
    cursor.execute("SELECT count(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM users WHERE registered = 1")
    registered = cursor.fetchone()[0]

    cursor.execute("SELECT count(*) FROM users WHERE registered = 0")
    pending = cursor.fetchone()[0]

    try:
        channel_count = await bot.get_chat_member_count(CHANNEL_ID)
    except Exception:
        channel_count = "N/A"

    cursor.execute("SELECT sent_at, sent_count FROM broadcast_log ORDER BY id DESC LIMIT 1")
    last_bcast = cursor.fetchone()
    last_bcast_str = f"{last_bcast[0]} ({last_bcast[1]} ta)" if last_bcast else "Hech qachon"

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>TO'LIQ STATISTIKA</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Bot foydalanuvchilari:  <b>{total}</b>\n"
        f"✅ Ro'yxatdan o'tganlar:   <b>{registered}</b>\n"
        f"⏳ Hali o'tmаganlar:       <b>{pending}</b>\n"
        f"📢 Kanal obunachilari:     <b>{channel_count}</b>\n"
        f"📨 Oxirgi broadcast:       <b>{last_bcast_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Yangilangan: {datetime.now().strftime('%H:%M:%S')}"
    )


# ─── AUTO REMINDER ─────────────────────────────────────────────────────────────
async def auto_reminder():
    while True:
        await asyncio.sleep(10800)  # har 3 soatda
        cursor.execute("SELECT id FROM users WHERE registered = 0")
        for (uid,) in cursor.fetchall():
            if uid not in ADMINS:
                try:
                    await bot.send_message(
                        uid,
                        "👋 Salom! Konkursda hali qatnashmadingiz.\n"
                        "Tezroq ro'yxatdan o'ting va sovg'alarni yutib oling! 🎁"
                    )
                except Exception:
                    pass


# ─── /START ───────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def start(message: types.Message):
    uid = message.from_user.id
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, joined_at) VALUES (?, ?)",
        (uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

    if is_admin(uid):
        await message.answer(
            "👑 <b>Admin panel</b>\nXush kelibsiz, kuchli boshqaruvchi!",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🎉 <b>AZIZZOMBI KONKURSIGA XO'SH KELIBSIZ!</b>\n\n"
            "Ishtirok etish uchun quyidagi kanallarga obuna bo'ling,\n"
            "so'ng ✅ <b>Tekshirish</b> tugmasini bosing.",
            reply_markup=subscribe_keyboard(),
            parse_mode="HTML"
        )


# ─── CHECK SUBSCRIPTION ───────────────────────────────────────────────────────
@dp.callback_query(F.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=call.from_user.id)
        if member.status in ("member", "administrator", "creator"):
            await call.message.answer(
                "✅ <b>Ajoyib!</b> Endi '<b>🎁 Konkursga qatnash</b>' tugmasini bosing.",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )
        else:
            await call.answer("❌ Siz hali barcha kanallarga obuna bo'lmagansiz!", show_alert=True)
    except Exception:
        await call.answer("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.", show_alert=True)


# ─── PROFILE ──────────────────────────────────────────────────────────────────
@dp.message(F.text == "👤 Mening profilim")
async def profile(message: types.Message):
    cursor.execute("SELECT name, phone, joined_at, registered FROM users WHERE id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    name     = user[0] if user and user[0] else "Mehmon"
    phone    = user[1] if user and user[1] else "Kiritilmagan"
    joined   = user[2] if user and user[2] else "—"
    status   = "✅ Ishtirokchi" if user and user[3] == 1 else "⏳ Ro'yxatdan o'tmagan"

    await message.answer(
        f"👤 <b>PROFIL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 Ism: <b>{name}</b>\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n"
        f"☎️ Telefon: <b>{phone}</b>\n"
        f"📅 Ro'yxatdan o'tgan sana: <b>{joined}</b>\n"
        f"🏆 Holat: <b>{status}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# ─── PUBLIC STATS ─────────────────────────────────────────────────────────────
@dp.message(F.text == "📊 Statistika")
async def public_stats(message: types.Message):
    cursor.execute("SELECT count(*) FROM users WHERE registered = 1")
    cnt = cursor.fetchone()[0]
    await message.answer(
        f"📊 Hozirda <b>{cnt}</b> ta ishtirokchi konkursda qatnashmoqda! 🎉",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# ─── CONTEST REGISTRATION ─────────────────────────────────────────────────────
@dp.message(F.text == "🎁 Konkursga qatnash")
async def start_contest(message: types.Message, state: FSMContext):
    cursor.execute("SELECT registered FROM users WHERE id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await message.answer("⚠️ Siz allaqachon konkursda qatnashyapsiz! 🎉", reply_markup=main_menu())
    else:
        await message.answer("📝 Ishtirok etish uchun <b>pasport bo'yicha FIO</b>ingizni kiriting:", parse_mode="HTML")
        await state.set_state(Reg.fio)


@dp.callback_query(F.data == "join_contest")
async def join_contest_callback(call: types.CallbackQuery, state: FSMContext):
    cursor.execute("SELECT registered FROM users WHERE id = ?", (call.from_user.id,))
    user = cursor.fetchone()
    if user and user[0] == 1:
        await call.answer("⚠️ Siz allaqachon ro'yxatdan o'tgansiz!", show_alert=True)
    else:
        await call.message.answer("📝 <b>Pasport bo'yicha FIO</b>ingizni kiriting:", parse_mode="HTML")
        await state.set_state(Reg.fio)


@dp.message(Reg.fio)
async def get_fio(message: types.Message, state: FSMContext):
    await state.update_data(fio=message.text)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Raqamni yuborish", request_contact=True)]],
        resize_keyboard=True
    )
    await message.answer("✅ FIO qabul qilindi! Endi telefon raqamingizni yuboring:", reply_markup=kb)
    await state.set_state(Reg.phone)


@dp.message(Reg.phone, F.contact)
async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE users SET name=?, phone=?, registered=1, joined_at=? WHERE id=?",
        (data["fio"], message.contact.phone_number, now, message.from_user.id)
    )
    conn.commit()
    await message.answer(
        "🎉 <b>Tabriklaymiz!</b>\n"
        "Siz muvaffaqiyatli ro'yxatdan o'tdingiz.\n"
        "G'olib bo'lishingizni tilaymiz! 🏆",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await state.clear()

    # Adminlarga xabar berish
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 <b>Yangi ishtirokchi!</b>\n"
                f"👤 {data['fio']}\n"
                f"☎️ {message.contact.phone_number}\n"
                f"🆔 <code>{message.from_user.id}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ─── ADMIN CONTACT ─────────────────────────────────────────────────────────────
@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: types.Message):
    await message.answer("✍️ Savollaringiz bo'lsa adminga yozing: https://t.me/zombiadminuz")


# ─── ADMIN CALLBACKS ──────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return

    data = call.data

    # ── Statistika
    if data == "admin_stats":
        text = await get_full_stats()
        await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")

    # ── Kanal
    elif data == "admin_chan_stats":
        try:
            count = await bot.get_chat_member_count(CHANNEL_ID)
            await call.answer(f"📢 Kanalda {count} ta obunachi bor.", show_alert=True)
        except Exception:
            await call.answer("❌ Bot kanal admini emas yoki xatolik yuz berdi.", show_alert=True)

    # ── Bot foydalanuvchilari
    elif data == "admin_bot_users":
        cursor.execute("SELECT count(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM users WHERE registered=1")
        reg = cursor.fetchone()[0]
        await call.answer(f"🤖 Jami: {total} ta\n✅ Ro'yxatdan o'tgan: {reg} ta", show_alert=True)

    # ── Ishtirokchilar ro'yxati
    elif data == "admin_users":
        cursor.execute("SELECT name, phone, joined_at FROM users WHERE registered = 1 ORDER BY joined_at DESC")
        users = cursor.fetchall()
        if not users:
            await call.answer("Ishtirokchilar hali yo'q.", show_alert=True)
            return
        lines = [f"{i+1}. {u[0]}  |  {u[1]}  |  {u[2] or '—'}" for i, u in enumerate(users)]
        text  = "👥 <b>ISHTIROKCHILAR RO'YXATI</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        # Telegram 4096 char limit
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await call.message.answer(chunk, parse_mode="HTML")

    # ── CSV export
    elif data == "admin_export":
        cursor.execute("SELECT id, name, phone, joined_at FROM users WHERE registered = 1")
        rows = cursor.fetchall()
        fname = f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(fname, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "FIO", "Telefon", "Ro'yxat sanasi"])
            writer.writerows(rows)
        await call.message.answer_document(
            FSInputFile(fname),
            caption=f"📥 <b>Jami {len(rows)} ta ishtirokchi</b>\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            parse_mode="HTML"
        )
        os.remove(fname)

    # ── Broadcast tarixi
    elif data == "admin_bcast_log":
        cursor.execute("SELECT sent_at, sent_count, fail_count FROM broadcast_log ORDER BY id DESC LIMIT 10")
        logs = cursor.fetchall()
        if not logs:
            await call.answer("Broadcast tarixi bo'sh.", show_alert=True)
            return
        lines = [f"📨 {l[0]}  ✅{l[1]}  ❌{l[2]}" for l in logs]
        await call.message.answer(
            "📋 <b>BROADCAST TARIXI</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines),
            parse_mode="HTML"
        )

    # ── Konkursni reset qilish
    elif data == "admin_reset_contest":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, tasdiqlash", callback_data="admin_reset_confirm"),
                InlineKeyboardButton(text="❌ Bekor qilish",   callback_data="admin_reset_cancel"),
            ]
        ])
        await call.message.answer(
            "⚠️ <b>DIQQAT!</b>\nBarcha ishtirokchilarni o'chirib, konkursni yangilashni xohlaysizmi?",
            reply_markup=kb,
            parse_mode="HTML"
        )

    # ── Mailing
    elif data == "admin_mailing":
        await call.message.answer("🖼 Rasm yuboring (broadcast uchun):")
        await state.set_state(Reg.mailing_photo)

    # ── G'olib aniqlash
    elif data == "admin_random":
        cursor.execute("SELECT count(*) FROM users WHERE registered=1")
        cnt = cursor.fetchone()[0]
        await call.message.answer(
            f"🎲 <b>G'OLI ANIQLASH</b>\n"
            f"Jami {cnt} ta ishtirokchi bor.\n\n"
            "Nechtа g'olib aniqlash kerak? (1–20):",
            parse_mode="HTML"
        )
        await state.set_state(Reg.random_count)

    # ── Ban
    elif data == "admin_ban":
        await call.message.answer("🚫 Bloklash uchun foydalanuvchi <b>Telegram ID</b>sini kiriting:", parse_mode="HTML")
        await state.set_state(Reg.ban_id)


# ─── RESET CONFIRM/CANCEL ─────────────────────────────────────────────────────
@dp.callback_query(F.data == "admin_reset_confirm")
async def reset_confirm(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cursor.execute("UPDATE users SET name=NULL, phone=NULL, registered=0, joined_at=NULL")
    conn.commit()
    await call.message.answer("✅ <b>Konkurs yangilandi!</b> Barcha ma'lumotlar o'chirildi.", parse_mode="HTML")


@dp.callback_query(F.data == "admin_reset_cancel")
async def reset_cancel(call: types.CallbackQuery):
    await call.message.answer("❌ Bekor qilindi.")


# ─── G'OLIB RANDOM ────────────────────────────────────────────────────────────
@dp.message(Reg.random_count)
async def process_random(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        count = int(message.text)
        if count < 1 or count > 20:
            raise ValueError
        cursor.execute("SELECT name, phone FROM users WHERE registered = 1")
        users = cursor.fetchall()
        if not users:
            await message.answer("⚠️ Ishtirokchilar hali yo'q!")
        else:
            winners = random.sample(users, min(count, len(users)))
            lines   = [f"🥇 {i+1}. <b>{w[0]}</b>  ☎️ {w[1]}" for i, w in enumerate(winners)]
            text    = (
                f"🎉 <b>G'OLIBLAR ANIQLANDI!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await message.answer(text, parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ Xatolik! 1 dan 20 gacha raqam kiriting.")


# ─── BAN USER ─────────────────────────────────────────────────────────────────
@dp.message(Reg.ban_id)
async def process_ban(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        target_id = int(message.text)
        cursor.execute("DELETE FROM users WHERE id = ?", (target_id,))
        conn.commit()
        await message.answer(f"🚫 <code>{target_id}</code> ID li foydalanuvchi bloklandi va o'chirildi.", parse_mode="HTML")
        try:
            await bot.send_message(target_id, "🚫 Siz konkursdan chetlashtirilgansiz.")
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Noto'g'ri ID. Iltimos, raqam kiriting.")
    await state.clear()


# ─── MAILING ──────────────────────────────────────────────────────────────────
@dp.message(Reg.mailing_photo, F.photo)
async def get_mailing_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("✍️ Endi konkurs tavsifini (matn) yozing:")
    await state.set_state(Reg.mailing_text)


@dp.message(Reg.mailing_text)
async def get_mailing_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")],
        [InlineKeyboardButton(text="🎬 YouTube",  url="https://www.youtube.com/@Azizzombistrim")],
        [InlineKeyboardButton(text="🎮 Kick",     url="https://kick.com/aziz-zombi")],
        [InlineKeyboardButton(text="✅ Ishtirok etish", callback_data="join_contest")],
    ])

    cursor.execute("SELECT id FROM users")
    users      = cursor.fetchall()
    sent, fail = 0, 0

    await message.answer(f"⏳ Broadcast boshlandi. {len(users)} ta foydalanuvchiga yuborilmoqda...")

    for (uid,) in users:
        try:
            await bot.send_photo(uid, data["photo"], caption=message.text, reply_markup=kb)
            sent += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)  # flood limit uchun

    cursor.execute(
        "INSERT INTO broadcast_log (sent_count, fail_count, sent_at) VALUES (?, ?, ?)",
        (sent, fail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()

    await message.answer(
        f"✅ <b>Broadcast tugadi!</b>\n"
        f"📨 Yuborildi: <b>{sent}</b>\n"
        f"❌ Muvaffaqiyatsiz: <b>{fail}</b>",
        parse_mode="HTML"
    )
    await state.clear()


# ─── WEB SERVER (keep-alive) ──────────────────────────────────────────────────
async def run_web():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot is running ✅"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()


# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    await run_web()
    asyncio.create_task(auto_reminder())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

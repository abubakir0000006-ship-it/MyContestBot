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
 
# ⚠️ MUHIM — BAZANI SAQLASH UCHUN ZAXIRA KANAL:
# Render bepul tarif xotirasi har deployda tozalanadi, shuning uchun baza (contest.db)
# vaqti-vaqti bilan shaxsiy (private) Telegram kanaliga avtomatik yuborib turiladi
# (xuddi "KINOFIKS ARXIV BOT" kabi), va bot qayta ishga tushganda shu kanaldan tiklab oladi.
#
# Sozlash uchun:
#   1. Yangi PRIVATE kanal yarating (faqat o'zingiz uchun, ishtirokchilarga ko'rinmaydi)
#   2. Botni shu kanalga ADMIN qilib qo'shing ("Xabar yuborish" va "Pin qilish" huquqlari bilan)
#   3. Kanalga istalgan bir xabar yuboring, keyin shu xabarni @username_to_id_bot ga forward qiling —
#      sizga -100 bilan boshlanadigan raqam (chat ID) qaytaradi
#   4. Shu raqamni pastga, BACKUP_CHAT_ID o'rniga qo'ying
#
# Sozlanmaguncha (0 turganda) bot oddiy ishlayveradi, faqat zaxira nusxa olinmaydi.
BACKUP_CHAT_ID = -1004307518213  # ✅ САЛИХ БОТ — zaxira kanal
 
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
 
# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = 'contest.db'
conn = None
cursor = None
 
 
def init_database():
    """Bazaga ulanish va jadvallarni yaratish. restore_database_if_needed() dan KEYIN chaqiriladi,
    shunda agar Render xotirani tozalagan bo'lsa, eski baza tiklab olingandan keyingina ulanamiz."""
    global conn, cursor
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
 
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY,
            name        TEXT,
            phone       TEXT,
            registered  INTEGER DEFAULT 0,
            joined_at   TEXT,
            ref_points  INTEGER DEFAULT 0,
            invited_by  INTEGER DEFAULT NULL,
            reward_sent INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS broadcast_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_count  INTEGER,
            fail_count  INTEGER,
            sent_at     TEXT
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id  INTEGER,
            invited_id  INTEGER UNIQUE,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS admin_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id    INTEGER,
            action      TEXT,
            details     TEXT,
            created_at  TEXT
        );
    """)
    conn.commit()
 
    # Eski bazalar uchun ustunlarni qo'shib qo'yamiz (agar mavjud bo'lmasa)
    for col, col_type in [("ref_points", "INTEGER DEFAULT 0"),
                           ("invited_by", "INTEGER DEFAULT NULL"),
                           ("reward_sent", "INTEGER DEFAULT 0"),
                           ("username", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
 
REFERRAL_GOAL   = 150              # nechta do'st taklif qilinganda mukofot beriladi
REFERRAL_REWARD = "200 000 so'm"   # mukofot matni
 
 
# ─── STATES ───────────────────────────────────────────────────────────────────
class Reg(StatesGroup):
    fio           = State()
    phone         = State()
    mailing_text  = State()
    mailing_photo = State()
    random_count  = State()
    ban_id        = State()
    broadcast_confirm = State()
    search_query      = State()
    seg_mailing_photo = State()
    seg_mailing_text  = State()
 
 
# ─── FOYDALANUVCHI KLAVIATURALARI (o'zbek tilida) ──────────────────────────────
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="🎁 Konkursga qatnash")],
        [KeyboardButton(text="👫 Do'stlarim"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="👨‍💻 Admin")]
    ], resize_keyboard=True)
 
 
def profile_inline_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👫 Do'st qo'shish (taklif havolasi)", callback_data="get_ref_link")]
    ])
 
 
def friends_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Taklif havolamni olish", callback_data="get_ref_link")],
        [InlineKeyboardButton(text="📋 Taklif qilganlarim", callback_data="my_referrals_list")],
        [InlineKeyboardButton(text="🏆 TOP-10 do'stlar reytingi", callback_data="top10_referrals")]
    ])
 
 
def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 TELEGRAM", url="https://t.me/+ZQzR8IaB1OU1MDdi")],
        [InlineKeyboardButton(text="🎬 YouTube",  url="https://www.youtube.com/@Azizzombistrim")],
        [InlineKeyboardButton(text="🎮 Kick",     url="https://kick.com/aziz-zombi")],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")],
    ])
 
 
# ─── ADMIN KLAVIATURALARI (rus tilida) ─────────────────────────────────────────
def admin_main_kb():
    """Pastki (reply) klaviatura — admin panelning asosiy bo'limlari."""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="👥 Участники")],
        [KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="🎁 Конкурс")],
        [KeyboardButton(text="🚫 Модерация")],
    ], resize_keyboard=True)
 
 
def admin_stats_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Общая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📊 Рост по дням",      callback_data="admin_growth")],
    ])
 
 
def admin_participants_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список участников", callback_data="admin_users")],
        [InlineKeyboardButton(text="📥 Скачать CSV",       callback_data="admin_export")],
        [InlineKeyboardButton(text="🔍 Поиск",             callback_data="admin_search")],
        [InlineKeyboardButton(text="👤 Все username",      callback_data="admin_usernames")],
    ])
 
 
def admin_mailing_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Всем",                callback_data="admin_mailing")],
        [InlineKeyboardButton(text="🎯 По аудитории",        callback_data="admin_segment_mailing")],
        [InlineKeyboardButton(text="📋 История рассылок",    callback_data="admin_bcast_log")],
    ])
 
 
def admin_contest_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Выбрать победителя",  callback_data="admin_random")],
        [InlineKeyboardButton(text="🏆 Топ по рефералам",    callback_data="admin_ref_top")],
        [InlineKeyboardButton(text="📥 CSV рефералов",       callback_data="admin_ref_export")],
        [InlineKeyboardButton(text="🔄 Сбросить конкурс",    callback_data="admin_reset_contest")],
    ])
 
 
def admin_moderation_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать",       callback_data="admin_ban")],
        [InlineKeyboardButton(text="📜 Журнал действий",     callback_data="admin_log_view")],
        [InlineKeyboardButton(text="💾 Сделать бэкап базы",  callback_data="admin_backup_now")],
    ])
 
 
CATEGORY_MAP = {
    "stats":        ("📊 Раздел: Статистика\nВыберите действие:",   admin_stats_kb),
    "participants": ("👥 Раздел: Участники\nВыберите действие:",    admin_participants_kb),
    "mailing":      ("📢 Раздел: Рассылка\nВыберите действие:",     admin_mailing_kb),
    "contest":      ("🎁 Раздел: Конкурс\nВыберите действие:",      admin_contest_kb),
    "moderation":   ("🚫 Раздел: Модерация\nВыберите действие:",    admin_moderation_kb),
}
 
 
def with_back(category: str):
    """Natija xabariga 'Orqaga' (rus: Назад) tugmasini qo'shadi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"backmenu_{category}")]
    ])
 
 
# ─── HELPERS ──────────────────────────────────────────────────────────────────
def is_admin(uid: int) -> bool:
    return uid in ADMINS
 
 
def log_admin_action(admin_id: int, action: str, details: str = ""):
    """Admin amalini jurnalga yozadi (statistikani buzmaydi, faqat tarix uchun)."""
    try:
        cursor.execute(
            "INSERT INTO admin_log (admin_id, action, details, created_at) VALUES (?, ?, ?, ?)",
            (admin_id, action, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    except Exception:
        pass
 
 
async def restore_database_if_needed():
    """Render yangi deploy paytida xotirani tozalagan bo'lsa (mahalliy fayl yo'q/bo'sh),
    eng so'nggi zaxira nusxani BACKUP_CHAT_ID dagi pin qilingan xabardan tiklab oladi."""
    if not BACKUP_CHAT_ID:
        logging.warning("BACKUP_CHAT_ID sozlanmagan — zaxira nusxa o'chirilgan, baza yangidan boshlanadi.")
        return
    if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 0:
        return  # mahalliy baza allaqachon bor — uni qayta yozib yubormaymiz
    try:
        chat = await bot.get_chat(BACKUP_CHAT_ID)
        pinned = chat.pinned_message
        if pinned and pinned.document:
            file_info = await bot.get_file(pinned.document.file_id)
            await bot.download_file(file_info.file_path, destination=DB_PATH)
            logging.info("✅ Baza zaxira nusxadan muvaffaqiyatli tiklandi.")
        else:
            logging.info("Zaxira kanalida hali pin qilingan baza fayli yo'q — yangi baza yaratiladi.")
    except Exception as e:
        logging.warning(f"Bazani tiklashda xatolik: {e}")
 
 
async def backup_database():
    """Joriy bazani BACKUP_CHAT_ID kanaliga fayl sifatida yuboradi va pin qiladi."""
    if not BACKUP_CHAT_ID:
        return
    try:
        cursor.execute("SELECT count(*) FROM users")
        total = cursor.fetchone()[0]
        msg = await bot.send_document(
            BACKUP_CHAT_ID,
            FSInputFile(DB_PATH),
            caption=(
                f"💾 #DB_BACKUP\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"👥 Пользователей в базе: {total}"
            )
        )
        await bot.pin_chat_message(BACKUP_CHAT_ID, msg.message_id, disable_notification=True)
    except Exception as e:
        logging.warning(f"Bazani zaxiralashda xatolik: {e}")
 
 
async def auto_backup():
    """Har 30 daqiqada avtomatik zaxira nusxa oladi."""
    while True:
        await asyncio.sleep(1800)
        await backup_database()
 
 
def progress_bar(points: int, goal: int, length: int = 10) -> str:
    """Vizual progress-bar: ▓▓▓▓░░░░░░ 40/150"""
    points = max(0, min(points, goal))
    filled = int(length * points / goal) if goal else 0
    return "▓" * filled + "░" * (length - filled)
 
 
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
    last_bcast_str = f"{last_bcast[0]} ({last_bcast[1]} шт.)" if last_bcast else "Ещё не было"
 
    cursor.execute("SELECT count(*) FROM referrals")
    total_refs = cursor.fetchone()[0]
 
    cursor.execute("SELECT count(*) FROM users WHERE reward_sent = 1")
    winners_cnt = cursor.fetchone()[0]
 
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>ПОЛНАЯ СТАТИСТИКА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей в боте:    <b>{total}</b>\n"
        f"✅ Зарегистрировано:        <b>{registered}</b>\n"
        f"⏳ Ещё не зарегистрированы: <b>{pending}</b>\n"
        f"📢 Подписчиков канала:      <b>{channel_count}</b>\n"
        f"👫 Всего рефералов:         <b>{total_refs}</b>\n"
        f"🏆 Получили награду:        <b>{winners_cnt}</b>\n"
        f"📨 Последняя рассылка:      <b>{last_bcast_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
    )
 
 
async def notify_referral(inviter_id: int, invited_id: int, invited_name: str):
    """Yangi do'st qo'shilganda chaqiruvchiga (o'zbekcha) va adminlarga (ruscha) xabar beradi,
    150 taklifga yetganda mukofot haqida alohida bildirishnoma yuboriladi."""
    cursor.execute("SELECT ref_points, reward_sent, name FROM users WHERE id = ?", (inviter_id,))
    row = cursor.fetchone()
    if not row:
        return
    points, reward_sent, inviter_name = row
    inviter_name = inviter_name or str(inviter_id)
 
    # ── Chaqiruvchiga xabar (o'zbek tilida — foydalanuvchi tomoni)
    try:
        await bot.send_message(
            inviter_id,
            f"🎉 <b>Yangi do'st qo'shildi!</b>\n"
            f"👤 {invited_name}\n"
            f"⭐ Sizning ballaringiz: <b>{points}/{REFERRAL_GOAL}</b>\n\n"
            f"Mukofot: <b>{REFERRAL_REWARD}</b> ({REFERRAL_GOAL} ta do'st uchun)",
            parse_mode="HTML"
        )
    except Exception:
        pass
 
    # ── Adminlarga xabar (rus tilida — admin tomoni)
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"👫 <b>Новый реферал!</b>\n"
                f"🙋 Пригласил: <b>{inviter_name}</b> (<code>{inviter_id}</code>)\n"
                f"🆕 Присоединился: <b>{invited_name}</b> (<code>{invited_id}</code>)\n"
                f"⭐ Текущий балл: <b>{points}/{REFERRAL_GOAL}</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
 
    # ── Maqsadga yetganda (150 ta do'st)
    if points >= REFERRAL_GOAL and not reward_sent:
        cursor.execute("UPDATE users SET reward_sent = 1 WHERE id = ?", (inviter_id,))
        conn.commit()
        try:
            await bot.send_message(
                inviter_id,
                f"🏆 <b>TABRIKLAYMIZ!</b>\n"
                f"Siz <b>{REFERRAL_GOAL}</b> ta do'st taklif qildingiz!\n"
                f"🎁 Mukofotingiz: <b>{REFERRAL_REWARD}</b>\n\n"
                f"Mukofotni olish uchun admin bilan bog'laning: https://t.me/zombiadminuz",
                parse_mode="HTML"
            )
        except Exception:
            pass
        for admin_id in ADMINS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🏆🔥 <b>НАЙДЕН ПОБЕДИТЕЛЬ! Нужно выдать награду!</b>\n"
                    f"👤 <b>{inviter_name}</b>\n"
                    f"🆔 <code>{inviter_id}</code>\n"
                    f"⭐ Баллы: <b>{points}/{REFERRAL_GOAL}</b>\n"
                    f"🎁 Награда: <b>{REFERRAL_REWARD}</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
 
    # ── Maqsadgacha oz qoldi — qo'shimcha rag'bat (faqat hali g'olib bo'lmaganlarga)
    elif not reward_sent and (REFERRAL_GOAL - points) in (5, 3, 1):
        left = REFERRAL_GOAL - points
        try:
            await bot.send_message(
                inviter_id,
                f"🔥 <b>Deyarli yetib keldingiz!</b>\n"
                f"Mukofotgacha yana faqat <b>{left}</b> ta do'st qoldi!\n"
                f"{progress_bar(points, REFERRAL_GOAL)}  {points}/{REFERRAL_GOAL}",
                parse_mode="HTML"
            )
        except Exception:
            pass
 
 
# ─── AUTO REMINDER ─────────────────────────────────────────────────────────────
async def auto_reminder():
    while True:
        await asyncio.sleep(43200)  # har 12 soatda
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
 
    cursor.execute("SELECT id FROM users WHERE id = ?", (uid,))
    already_exists = cursor.fetchone() is not None
 
    cursor.execute(
        "INSERT OR IGNORE INTO users (id, joined_at) VALUES (?, ?)",
        (uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
 
    # Username'ni har doim yangilab turamiz (odam username o'zgartirsa ham bazada yangi bo'lsin)
    cursor.execute("UPDATE users SET username = ? WHERE id = ?", (message.from_user.username, uid))
    conn.commit()
 
    # ── Referal havola orqali kirgan bo'lsa
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            inviter_id = int(args[1].replace("ref_", ""))
        except ValueError:
            inviter_id = None
 
        if inviter_id and inviter_id != uid:
            cursor.execute("SELECT invited_by FROM users WHERE id = ?", (uid,))
            row = cursor.fetchone()
            if row and row[0] is None:
                cursor.execute("SELECT id FROM users WHERE id = ?", (inviter_id,))
                if cursor.fetchone():
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO referrals (inviter_id, invited_id, created_at) VALUES (?, ?, ?)",
                            (inviter_id, uid, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        )
                        cursor.execute("UPDATE users SET invited_by = ? WHERE id = ?", (inviter_id, uid))
                        cursor.execute("UPDATE users SET ref_points = ref_points + 1 WHERE id = ?", (inviter_id,))
                        conn.commit()
                        await notify_referral(inviter_id, uid, message.from_user.full_name)
                    except Exception:
                        pass
 
    if is_admin(uid):
        await message.answer(
            "👑 <b>Панель администратора</b>\n"
            "Добро пожаловать! Выберите раздел в меню внизу 👇",
            reply_markup=admin_main_kb(),
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
    cursor.execute(
        "SELECT name, phone, joined_at, registered, ref_points FROM users WHERE id = ?",
        (message.from_user.id,)
    )
    user = cursor.fetchone()
    name     = user[0] if user and user[0] else "Mehmon"
    phone    = user[1] if user and user[1] else "Kiritilmagan"
    joined   = user[2] if user and user[2] else "—"
    status   = "✅ Ishtirokchi" if user and user[3] == 1 else "⏳ Ro'yxatdan o'tmagan"
    points   = user[4] if user and user[4] else 0
 
    await message.answer(
        f"👤 <b>PROFIL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 Ism: <b>{name}</b>\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n"
        f"☎️ Telefon: <b>{phone}</b>\n"
        f"📅 Ro'yxatdan o'tgan sana: <b>{joined}</b>\n"
        f"🏆 Holat: <b>{status}</b>\n"
        f"👫 Taklif qilingan do'stlar: <b>{points}/{REFERRAL_GOAL}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 Do'st qo'shib, <b>{REFERRAL_REWARD}</b> yutib oling!",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await message.answer(
        "👫 Do'stlarni taklif qiling va mukofot yutib oling:",
        reply_markup=profile_inline_kb()
    )
    await message.answer(
        f"📊 <b>Mukofotgacha progress:</b>\n"
        f"{progress_bar(points, REFERRAL_GOAL)}  {points}/{REFERRAL_GOAL}",
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
 
 
# ─── DO'STLARIM (REFERAL) ──────────────────────────────────────────────────────
@dp.message(F.text == "👫 Do'stlarim")
async def friends_menu(message: types.Message):
    cursor.execute("SELECT ref_points FROM users WHERE id = ?", (message.from_user.id,))
    row = cursor.fetchone()
    points = row[0] if row and row[0] else 0
    left = max(REFERRAL_GOAL - points, 0)
 
    await message.answer(
        f"👫 <b>DO'STLAR TIZIMI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"1 do'st = 1 ball ⭐\n"
        f"{REFERRAL_GOAL} ball = <b>{REFERRAL_REWARD}</b> 🎁\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Sizning ballaringiz: <b>{points}/{REFERRAL_GOAL}</b>\n"
        f"🎯 Mukofotgacha qoldi: <b>{left}</b> ta do'st\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        reply_markup=friends_menu_kb(),
        parse_mode="HTML"
    )
 
 
@dp.callback_query(F.data == "get_ref_link")
async def get_ref_link(call: types.CallbackQuery):
    uid = call.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
 
    cursor.execute("SELECT ref_points FROM users WHERE id = ?", (uid,))
    row = cursor.fetchone()
    points = row[0] if row and row[0] else 0
 
    share_text = "AzizZombi konkursiga qatnash va sovg'a yutib ol! 🎁"
    share_url  = f"https://t.me/share/url?url={link}&text={share_text}"
 
    await call.message.answer(
        f"🔗 <b>Sizning shaxsiy taklif havolangiz:</b>\n"
        f"<a href=\"{link}\">{link}</a>\n\n"
        f"Ushbu havolani do'stlaringizga yuboring. Ular shu havola orqali botga kirsa,\n"
        f"sizga <b>1 ball</b> qo'shiladi! ⭐\n\n"
        f"Hozirgi ballaringiz: <b>{points}/{REFERRAL_GOAL}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Do'stlarga yuborish", url=share_url)]
        ]),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await call.answer()
 
 
@dp.callback_query(F.data == "my_referrals_list")
async def my_referrals_list(call: types.CallbackQuery):
    uid = call.from_user.id
    cursor.execute(
        "SELECT u.name, u.id, r.created_at FROM referrals r "
        "JOIN users u ON u.id = r.invited_id WHERE r.inviter_id = ? ORDER BY r.created_at DESC",
        (uid,)
    )
    refs = cursor.fetchall()
    if not refs:
        await call.answer("Siz hali hech kimni taklif qilmadingiz.", show_alert=True)
        return
 
    lines = [f"{i+1}. {r[0] or 'Foydalanuvchi'}  |  <code>{r[1]}</code>  |  {r[2]}" for i, r in enumerate(refs)]
    text = (
        f"📋 <b>SIZ TAKLIF QILGAN DO'STLAR</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━\nJami: <b>{len(refs)}</b> ta"
    )
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        await call.message.answer(chunk, parse_mode="HTML")
    await call.answer()
 
 
@dp.callback_query(F.data == "top10_referrals")
async def top10_referrals(call: types.CallbackQuery):
    cursor.execute(
        "SELECT name, ref_points FROM users WHERE ref_points > 0 ORDER BY ref_points DESC LIMIT 10"
    )
    rows = cursor.fetchall()
    if not rows:
        await call.answer("Hali reyting bo'sh, birinchi bo'ling! 🚀", show_alert=True)
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, pts) in enumerate(rows):
        mark = medals[i] if i < 3 else f"{i+1}."
        display_name = (name or "Foydalanuvchi")
        lines.append(f"{mark} {display_name} — {pts} ta do'st")
    text = (
        "🏆 <b>TOP-10 DO'STLAR REYTINGI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines) +
        "\n━━━━━━━━━━━━━━━━━━━━\nSiz ham TOP-ga chiqishingiz mumkin! 🚀"
    )
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()
 
 
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
 
    # Adminlarga xabar berish (rus tilida — admin tomoni)
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 <b>Новый участник!</b>\n"
                f"👤 {data['fio']}\n"
                f"☎️ {message.contact.phone_number}\n"
                f"🆔 <code>{message.from_user.id}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
 
 
# ─── ADMIN CONTACT (foydalanuvchi tomoni) ──────────────────────────────────────
@dp.message(F.text == "👨‍💻 Admin")
async def admin_contact(message: types.Message):
    await message.answer("✍️ Savollaringiz bo'lsa adminga yozing: https://t.me/zombiadminuz")
 
 
# ─── ADMIN: BO'LIM TUGMALARI (pastki klaviatura, rus tilida) ───────────────────
@dp.message(F.text == "📊 Статистика")
async def menu_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    text, kb_func = CATEGORY_MAP["stats"]
    await message.answer(text, reply_markup=kb_func())
 
 
@dp.message(F.text == "👥 Участники")
async def menu_participants(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    text, kb_func = CATEGORY_MAP["participants"]
    await message.answer(text, reply_markup=kb_func())
 
 
@dp.message(F.text == "📢 Рассылка")
async def menu_mailing(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    text, kb_func = CATEGORY_MAP["mailing"]
    await message.answer(text, reply_markup=kb_func())
 
 
@dp.message(F.text == "🎁 Конкурс")
async def menu_contest(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    text, kb_func = CATEGORY_MAP["contest"]
    await message.answer(text, reply_markup=kb_func())
 
 
@dp.message(F.text == "🚫 Модерация")
async def menu_moderation(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    text, kb_func = CATEGORY_MAP["moderation"]
    await message.answer(text, reply_markup=kb_func())
 
 
# ─── ADMIN: "ORQAGA / НАЗАД" TUGMASI ───────────────────────────────────────────
@dp.callback_query(F.data.startswith("backmenu_"))
async def back_to_category(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    await state.clear()  # bo'limlar orasida o'tishda eski "kutilayotgan input" holatini tozalaymiz
    cat = call.data.replace("backmenu_", "")
    entry = CATEGORY_MAP.get(cat)
    if entry:
        text, kb_func = entry
        await call.message.answer(text, reply_markup=kb_func())
    await call.answer()
 
 
# ─── ADMIN CALLBACKS (asosiy amallar) ──────────────────────────────────────────
@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
 
    data = call.data
 
    # ── Статистика
    if data == "admin_stats":
        text = await get_full_stats()
        await call.message.answer(text, reply_markup=with_back("stats"), parse_mode="HTML")
 
    # ── Рост по дням
    elif data == "admin_growth":
        cursor.execute("""
            SELECT substr(joined_at, 1, 10) as day, count(*) as cnt
            FROM users
            WHERE joined_at IS NOT NULL
            GROUP BY day
            ORDER BY day DESC
            LIMIT 7
        """)
        rows = cursor.fetchall()
        if not rows:
            await call.answer("Нет данных.", show_alert=True)
            return
        max_cnt = max(r[1] for r in rows) or 1
        lines = []
        for day, cnt in rows:
            bar_len = int((cnt / max_cnt) * 15)
            lines.append(f"{day}  {'▓' * bar_len}{'░' * (15 - bar_len)}  {cnt} шт.")
        text = (
            "📈 <b>РОСТ ПО ДНЯМ (последние 7 дней)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        )
        await call.message.answer(text, reply_markup=with_back("stats"), parse_mode="HTML")
 
    # ── Список участников
    elif data == "admin_users":
        cursor.execute("SELECT name, phone, joined_at FROM users WHERE registered = 1 ORDER BY joined_at DESC")
        users = cursor.fetchall()
        if not users:
            await call.answer("Участников пока нет.", show_alert=True)
            return
        lines = [f"{i+1}. {u[0]}  |  {u[1]}  |  {u[2] or '—'}" for i, u in enumerate(users)]
        text  = "👥 <b>СПИСОК УЧАСТНИКОВ</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            await call.message.answer(chunk, reply_markup=with_back("participants") if is_last else None, parse_mode="HTML")
 
    # ── CSV скачать
    elif data == "admin_export":
        cursor.execute("SELECT id, name, phone, joined_at FROM users WHERE registered = 1")
        rows = cursor.fetchall()
        fname = f"users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(fname, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "ФИО", "Телефон", "Дата регистрации"])
            writer.writerows(rows)
        await call.message.answer_document(
            FSInputFile(fname),
            caption=f"📥 <b>Всего участников: {len(rows)}</b>\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            reply_markup=with_back("participants"),
            parse_mode="HTML"
        )
        os.remove(fname)
 
    # ── История рассылок
    elif data == "admin_bcast_log":
        cursor.execute("SELECT sent_at, sent_count, fail_count FROM broadcast_log ORDER BY id DESC LIMIT 10")
        logs = cursor.fetchall()
        if not logs:
            await call.answer("История пуста.", show_alert=True)
            return
        lines = [f"📨 {l[0]}  ✅{l[1]}  ❌{l[2]}" for l in logs]
        await call.message.answer(
            "📋 <b>ИСТОРИЯ РАССЫЛОК</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines),
            reply_markup=with_back("mailing"),
            parse_mode="HTML"
        )
 
    # ── Сбросить конкурс
    elif data == "admin_reset_contest":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, подтвердить", callback_data="admin_reset_confirm"),
                InlineKeyboardButton(text="❌ Отмена",          callback_data="admin_reset_cancel"),
            ]
        ])
        await call.message.answer(
            "⚠️ <b>ВНИМАНИЕ!</b>\nВы уверены, что хотите удалить всех участников и обновить конкурс?",
            reply_markup=kb,
            parse_mode="HTML"
        )
 
    # ── Рассылка всем
    elif data == "admin_mailing":
        await call.message.answer("🖼 Отправьте фото (для общей рассылки):")
        await state.set_state(Reg.mailing_photo)
 
    # ── Выбрать победителя
    elif data == "admin_random":
        cursor.execute("SELECT count(*) FROM users WHERE registered=1")
        cnt = cursor.fetchone()[0]
        await call.message.answer(
            f"🎲 <b>ВЫБОР ПОБЕДИТЕЛЯ</b>\n"
            f"Всего участников: {cnt}\n\n"
            "Сколько победителей выбрать? (1–20):",
            parse_mode="HTML"
        )
        await state.set_state(Reg.random_count)
 
    # ── Блокировка
    elif data == "admin_ban":
        await call.message.answer("🚫 Введите Telegram <b>ID</b> пользователя для блокировки:", parse_mode="HTML")
        await state.set_state(Reg.ban_id)
 
    # ── Топ по рефералам
    elif data == "admin_ref_top":
        cursor.execute(
            "SELECT name, id, ref_points FROM users WHERE ref_points > 0 ORDER BY ref_points DESC LIMIT 30"
        )
        rows = cursor.fetchall()
        if not rows:
            await call.answer("Пока никто не привёл друзей.", show_alert=True)
            return
        lines = []
        for i, (name, uid2, pts) in enumerate(rows):
            mark = "🏆" if pts >= REFERRAL_GOAL else "⭐"
            lines.append(f"{i+1}. {mark} {name or 'Без имени'}  |  <code>{uid2}</code>  |  {pts}/{REFERRAL_GOAL}")
        text = (
            "🏆 <b>РЕЙТИНГ РЕФЕРАЛОВ (ТОП-30)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        )
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            await call.message.answer(chunk, reply_markup=with_back("contest") if is_last else None, parse_mode="HTML")
 
    # ── CSV рефералов
    elif data == "admin_ref_export":
        cursor.execute(
            "SELECT inviter_id, invited_id, created_at FROM referrals ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        if not rows:
            await call.answer("Данных о рефералах нет.", show_alert=True)
            return
        fname = f"referrals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(fname, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["ID приглашающего", "ID приглашённого", "Дата"])
            writer.writerows(rows)
        await call.message.answer_document(
            FSInputFile(fname),
            caption=f"📥 <b>Всего рефералов: {len(rows)}</b>\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            reply_markup=with_back("contest"),
            parse_mode="HTML"
        )
        os.remove(fname)
 
    # ── Поиск пользователя (ID, телефон, username, имя)
    elif data == "admin_search":
        await call.message.answer(
            "🔍 Введите <b>ID</b>, <b>телефон</b>, <b>username</b> или <b>имя</b> для поиска:",
            parse_mode="HTML"
        )
        await state.set_state(Reg.search_query)
 
    # ── Все username
    elif data == "admin_usernames":
        cursor.execute(
            "SELECT id, username, name, registered FROM users ORDER BY (username IS NULL), id DESC"
        )
        rows = cursor.fetchall()
        if not rows:
            await call.answer("Пользователей нет.", show_alert=True)
            return
        lines = []
        for i, (uid2, uname, name, reg) in enumerate(rows):
            uname_str = f"@{uname}" if uname else "— (нет username)"
            status = "✅" if reg == 1 else "⏳"
            name_display = name or "Без имени"
            lines.append(f"{i+1}. {status} {uname_str}  |  {name_display}  |  <code>{uid2}</code>")
        text = (
            "👤 <b>ВСЕ ПОЛЬЗОВАТЕЛИ (USERNAME)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        )
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            await call.message.answer(chunk, reply_markup=with_back("participants") if is_last else None, parse_mode="HTML")
 
    # ── Журнал действий администратора
    elif data == "admin_log_view":
        cursor.execute(
            "SELECT admin_id, action, details, created_at FROM admin_log ORDER BY id DESC LIMIT 20"
        )
        rows = cursor.fetchall()
        if not rows:
            await call.answer("Журнал пуст.", show_alert=True)
            return
        lines = [f"🕐 {r[3]}  |  👤 <code>{r[0]}</code>  |  {r[1]} ({r[2]})" for r in rows]
        text = "📜 <b>ЖУРНАЛ ДЕЙСТВИЙ АДМИНИСТРАТОРА</b>\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            await call.message.answer(chunk, reply_markup=with_back("moderation") if is_last else None, parse_mode="HTML")
 
    # ── Сегментированная (целевая) рассылка
    elif data == "admin_segment_mailing":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Всем", callback_data="seg_all")],
            [InlineKeyboardButton(text="✅ Только зарегистрированным", callback_data="seg_registered")],
            [InlineKeyboardButton(text="⏳ Только незарегистрированным", callback_data="seg_pending")],
        ])
        await call.message.answer("🎯 Кому отправить сообщение?", reply_markup=kb)
 
    # ── Резервная копия базы (вручную)
    elif data == "admin_backup_now":
        if not BACKUP_CHAT_ID:
            await call.answer("⚠️ BACKUP_CHAT_ID не настроен в коде! Резервное копирование выключено.", show_alert=True)
            return
        await call.message.answer("⏳ Создаю резервную копию базы...")
        await backup_database()
        log_admin_action(call.from_user.id, "Ручной бэкап", "Запущен вручную из панели")
        await call.message.answer(
            "✅ Резервная копия отправлена в канал-хранилище.",
            reply_markup=with_back("moderation")
        )
 
 
# ─── RESET CONFIRM/CANCEL ─────────────────────────────────────────────────────
@dp.callback_query(F.data == "admin_reset_confirm")
async def reset_confirm(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cursor.execute("UPDATE users SET name=NULL, phone=NULL, registered=0, joined_at=NULL")
    conn.commit()
    log_admin_action(call.from_user.id, "Сброс конкурса", "Данные всех участников очищены")
    await call.message.answer(
        "✅ <b>Конкурс обновлён!</b> Все данные удалены.",
        reply_markup=with_back("contest"),
        parse_mode="HTML"
    )
 
 
@dp.callback_query(F.data == "admin_reset_cancel")
async def reset_cancel(call: types.CallbackQuery):
    await call.message.answer("❌ Отменено.")
 
 
# ─── ВЫБОР ПОБЕДИТЕЛЯ ───────────────────────────────────────────────────────────
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
            await message.answer("⚠️ Участников пока нет!")
        else:
            winners = random.sample(users, min(count, len(users)))
            lines   = [f"🥇 {i+1}. <b>{w[0]}</b>  ☎️ {w[1]}" for i, w in enumerate(winners)]
            text    = (
                f"🎉 <b>ПОБЕДИТЕЛИ ОПРЕДЕЛЕНЫ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                + "\n".join(lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await message.answer(text, reply_markup=with_back("contest"), parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ Ошибка! Введите число от 1 до 20.")
 
 
# ─── БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ ────────────────────────────────────────────────────
@dp.message(Reg.ban_id)
async def process_ban(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        target_id = int(message.text)
        cursor.execute("DELETE FROM users WHERE id = ?", (target_id,))
        conn.commit()
        log_admin_action(message.from_user.id, "Блокировка пользователя", f"ID: {target_id}")
        await message.answer(
            f"🚫 Пользователь <code>{target_id}</code> заблокирован и удалён.",
            reply_markup=with_back("moderation"),
            parse_mode="HTML"
        )
        try:
            await bot.send_message(target_id, "🚫 Siz konkursdan chetlashtirilgansiz.")
        except Exception:
            pass
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число.")
    await state.clear()
 
 
# ─── ПОИСК ПОЛЬЗОВАТЕЛЯ ─────────────────────────────────────────────────────────
@dp.message(Reg.search_query)
async def process_search(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    q = message.text.strip()
    cursor.execute("""
        SELECT id, name, phone, username, registered, ref_points, joined_at
        FROM users
        WHERE id = ? OR phone LIKE ? OR username LIKE ? OR name LIKE ?
        LIMIT 10
    """, (q if q.isdigit() else -1, f"%{q}%", f"%{q}%", f"%{q}%"))
    rows = cursor.fetchall()
    await state.clear()
    if not rows:
        await message.answer("❌ Ничего не найдено.", reply_markup=with_back("participants"))
        return
    lines = []
    for r in rows:
        uid2, name, phone, uname, reg, pts, joined = r
        uname_str = f"@{uname}" if uname else "—"
        status = "✅ Участник" if reg == 1 else "⏳ Не зарегистрирован"
        lines.append(
            f"🆔 ID: <code>{uid2}</code>\n"
            f"📛 Имя: {name or '—'}\n"
            f"👤 Username: {uname_str}\n"
            f"☎️ Телефон: {phone or '—'}\n"
            f"🏆 Статус: {status}\n"
            f"👫 Баллы за рефералов: {pts or 0}\n"
            f"📅 Дата регистрации: {joined or '—'}"
        )
    text = "🔍 <b>РЕЗУЛЬТАТЫ ПОИСКА</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(lines)
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        await message.answer(chunk, reply_markup=with_back("participants") if is_last else None, parse_mode="HTML")
 
 
# ─── СЕГМЕНТИРОВАННАЯ РАССЫЛКА ───────────────────────────────────────────────────
@dp.callback_query(F.data.in_(["seg_all", "seg_registered", "seg_pending"]))
async def seg_choose_audience(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Нет доступа!", show_alert=True)
        return
    await state.update_data(audience=call.data)
    await call.message.answer("🖼 Отправьте фото (для сегментированной рассылки):")
    await state.set_state(Reg.seg_mailing_photo)
 
 
@dp.message(Reg.seg_mailing_photo, F.photo)
async def seg_get_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("✍️ Теперь напишите текст сообщения:")
    await state.set_state(Reg.seg_mailing_text)
 
 
@dp.message(Reg.seg_mailing_text)
async def seg_get_text_and_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    audience = data.get("audience", "seg_all")
 
    if audience == "seg_registered":
        cursor.execute("SELECT id FROM users WHERE registered = 1")
        audience_label = "Только зарегистрированным"
    elif audience == "seg_pending":
        cursor.execute("SELECT id FROM users WHERE registered = 0")
        audience_label = "Только незарегистрированным"
    else:
        cursor.execute("SELECT id FROM users")
        audience_label = "Всем"
 
    users = cursor.fetchall()
    sent, fail = 0, 0
    await message.answer(f"⏳ Рассылка началась ({audience_label}). Отправка {len(users)} пользователям...")
 
    for (uid,) in users:
        try:
            await bot.send_photo(uid, data["photo"], caption=message.text)
            sent += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
 
    cursor.execute(
        "INSERT INTO broadcast_log (sent_count, fail_count, sent_at) VALUES (?, ?, ?)",
        (sent, fail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    log_admin_action(message.from_user.id, "Сегмент-рассылка", f"{audience_label}: ✅{sent} ❌{fail}")
 
    await message.answer(
        f"✅ <b>Сегмент-рассылка завершена!</b>\n"
        f"🎯 Аудитория: <b>{audience_label}</b>\n"
        f"📨 Отправлено: <b>{sent}</b>\n"
        f"❌ Не доставлено: <b>{fail}</b>",
        reply_markup=with_back("mailing"),
        parse_mode="HTML"
    )
    await state.clear()
 
 
# ─── РАССЫЛКА ВСЕМ ──────────────────────────────────────────────────────────────
@dp.message(Reg.mailing_photo, F.photo)
async def get_mailing_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("✍️ Теперь напишите текст сообщения (на узбекском — его увидят участники):")
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
 
    await message.answer(f"⏳ Рассылка началась. Отправка {len(users)} пользователям...")
 
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
    log_admin_action(message.from_user.id, "Общая рассылка", f"✅{sent} ❌{fail}")
 
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n"
        f"📨 Отправлено: <b>{sent}</b>\n"
        f"❌ Не доставлено: <b>{fail}</b>",
        reply_markup=with_back("mailing"),
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
    await restore_database_if_needed()
    init_database()
    await run_web()
    asyncio.create_task(auto_reminder())
    asyncio.create_task(auto_backup())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())

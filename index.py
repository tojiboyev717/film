import os
import json
import logging
import pymongo
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters
)
from telegram import ChatMember

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== CONFIG =====
TOKEN = "8342429220:AAHUExxMXZV9OhZav3kcbuz9YKu5avOW49E"
MAIN_ADMIN_ID = 6560139113
MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://user:pass@cluster.mongodb.net/test?retryWrites=true&w=majority")
try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client['telegram_bot']
except Exception as e:
    logger.error(f"MongoDB ulanishda xato: {e}")
    db = None

# Sticker ID (o'zingiznikiga almashtiring yoki o'chirib qo'ying)
FILM_STICKER_ID = "CAACAgIAAxkBAAIBB2aZ0vZ0vZ0vZ0vZ0vZ0vZ0vZ0"

# Limit sozlamalari
MAX_CODE_ATTEMPTS = 10
BLOCK_DURATION_MINUTES = 15

# ===== KEYBOARDS =====
def main_keyboard(is_admin=False):
    kb = []
    if is_admin:
        kb.append([InlineKeyboardButton("👑 Admin panel", callback_data='admin_panel')])
    return InlineKeyboardMarkup(kb) if kb else None

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_main')]])

def admin_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]])

# ===== ADMINLAR =====
def get_admins():
    if db is None:
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f).get("admins", [MAIN_ADMIN_ID])
        except Exception:
            return [MAIN_ADMIN_ID]
    doc = db.settings.find_one({"_id": "admins"})
    if not doc:
        db.settings.insert_one({"_id": "admins", "list": [MAIN_ADMIN_ID]})
        return [MAIN_ADMIN_ID]
    return doc.get("list", [MAIN_ADMIN_ID])

def check_is_admin(user_id):
    return user_id in get_admins()

def add_admin(admin_id):
    if admin_id == MAIN_ADMIN_ID:
        return False
    admins = get_admins()
    if admin_id not in admins:
        admins.append(admin_id)
        if db is not None:
            db.settings.update_one({"_id": "admins"}, {"$set": {"list": admins}}, upsert=True)
        else:
            try:
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
            settings["admins"] = admins
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    return False

def remove_admin(admin_id):
    if admin_id == MAIN_ADMIN_ID:
        return False
    admins = get_admins()
    if admin_id in admins:
        admins.remove(admin_id)
        if db is not None:
            db.settings.update_one({"_id": "admins"}, {"$set": {"list": admins}})
        else:
            try:
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
            settings["admins"] = admins
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    return False

# ===== DATA =====
def load_data():
    default = {
        "_id": "data",
        "movies": {},
        "users": {},
        "channel_link": "https://t.me/+FQ3XcZl0VUM4NTgy",
        "requests": {}
    }
    try:
        if db is None:
            with open("data.json", "r", encoding="utf-8") as f:
                doc = json.load(f)
        else:
            doc = db.bot_data.find_one({"_id": "data"})
            if not doc:
                db.bot_data.insert_one(default)
                return default
        
        doc.setdefault("users", {})
        doc.setdefault("movies", {})
        doc.setdefault("requests", {})
        for uid, info in doc["users"].items():
            if isinstance(info, dict):
                info.setdefault("code_attempts", 0)
                info.setdefault("block_until", 0)
        return doc
    except Exception as e:
        logger.error(f"Data yuklash xatosi: {e}")
        return default

def save_data(data):
    try:
        data["_id"] = "data"
        if db is not None:
            db.bot_data.replace_one({"_id": "data"}, data, upsert=True)
        else:
            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Data saqlash xatosi: {e}")

# ===== KANAL =====
def get_required_channels():
    if db is None:
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f).get("channels", [])
        except:
            return []
    try:
        doc = db.settings.find_one({"_id": "channels"})
        if not doc:
            return []
        return doc.get("list", [])
    except:
        return []

def add_required_channel(channel):
    if not (channel.startswith('@') or channel.startswith('http') or '|' in channel):
        return False
    channels = get_required_channels()
    if channel not in channels:
        channels.append(channel.strip())
        if db is not None:
            db.settings.update_one({"_id": "channels"}, {"$set": {"list": channels}}, upsert=True)
        else:
            try:
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except:
                settings = {}
            settings["channels"] = channels
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    return False

def remove_required_channel(channel):
    channels = get_required_channels()
    if channel in channels:
        channels.remove(channel)
        if db is not None:
            db.settings.update_one({"_id": "channels"}, {"$set": {"list": channels}}, upsert=True)
        else:
            try:
                with open("settings.json", "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except:
                settings = {}
            settings["channels"] = channels
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    return False

# ===== OBUNA =====
async def get_unsubscribed_channels(context, user_id, is_admin, required_channels):
    if is_admin or not required_channels:
        return []
    try:
        data = load_data()
        requests = data.get("requests", {})
        unsubscribed = []

        for channel in required_channels:
            if channel.startswith('http'):
                continue
            
            chat_id = channel
            if '|' in channel:
                chat_id = channel.split('|', 1)[0]
                
                if chat_id in requests and str(user_id) in requests[chat_id]:
                    continue

            try:
                member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    unsubscribed.append(channel)
            except:
                unsubscribed.append(channel)
        return unsubscribed
    except:
        return required_channels

async def show_subscription_prompt(update, context, unsubscribed_channels):
    if not unsubscribed_channels:
        return

    buttons = []
    for i, ch in enumerate(unsubscribed_channels, 1):
        if '|' in ch:
            chat_id, link = ch.split('|', 1)
            buttons.append([InlineKeyboardButton(f"{i} - kanal", url=link)])
        elif ch.startswith('http'):
            buttons.append([InlineKeyboardButton(f"{i} - kanal", url=ch)])
        else:
            name = ch[1:] if ch.startswith('@') else ch
            buttons.append([InlineKeyboardButton(f"{i} - kanal", url=f"https://t.me/{name}")])

    text = "❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak."

    buttons.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data='check_subscription')])

    kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(text, reply_markup=kb)
        except Exception:
            pass
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    uid = str(user.id)

    if "users" not in data:
        data["users"] = {}

    if uid not in data["users"]:
        data["users"][uid] = {
            "name": user.first_name,
            "username": user.username or "",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "code_attempts": 0,
            "block_until": 0
        }
        save_data(data)

    is_admin_user = check_is_admin(user.id)
    required_channels = get_required_channels()

    unsubscribed = await get_unsubscribed_channels(context, user.id, is_admin_user, required_channels)
    if unsubscribed:
        await show_subscription_prompt(update, context, unsubscribed)
        return

    greeting = (
        f"👋 Assalomu alaykum <i>{user.first_name}</i> botimizga xush kelibsiz.\n\n"
        "✍️ Kino kodini yuboring."
    )

    await update.message.reply_text(
        greeting,
        parse_mode="HTML",
        reply_markup=main_keyboard(is_admin_user)
    )

# ===== BUTTON CALLBACK =====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data != 'check_subscription':
        await q.answer()

    if q.data == 'delete_msg':
        try:
            await q.message.delete()
        except Exception:
            pass
        return
    data = load_data()
    user = q.from_user
    is_admin_user = check_is_admin(user.id)
    required_channels = get_required_channels()

    if q.data == 'check_subscription':
        unsubscribed = await get_unsubscribed_channels(context, user.id, is_admin_user, required_channels)
        if not unsubscribed:
            try:
                await q.answer("✅ Rahmat, obuna tasdiqlandi!", show_alert=True)
            except Exception:
                pass
            greeting = (
                f"👋 Assalomu alaykum <i>{user.first_name}</i> botimizga xush kelibsiz.\n\n"
                "✍️ Kino kodini yuboring."
            )
            try:
                await q.message.edit_text(
                    greeting,
                    parse_mode="HTML",
                    reply_markup=main_keyboard(is_admin_user)
                )
            except Exception:
                pass
        else:
            try:
                await q.answer("❌ Obuna bo'lmadingiz", show_alert=True)
            except Exception:
                pass
            await show_subscription_prompt(update, context, unsubscribed)
        return

    unsubscribed = await get_unsubscribed_channels(context, user.id, is_admin_user, required_channels)
    if unsubscribed:
        await show_subscription_prompt(update, context, unsubscribed)
        return

    if q.data == 'back_to_main':
        greeting = (
            f"👋 Assalomu alaykum <i>{user.first_name}</i> botimizga xush kelibsiz.\n\n"
            "✍️ Kino kodini yuboring."
        )
        await q.edit_message_text(
            greeting,
            parse_mode="HTML",
            reply_markup=main_keyboard(is_admin_user)
        )
        return

    if q.data == 'back_to_admin_panel':
        if not is_admin_user:
            await q.edit_message_text("Faqat admin uchun!")
            return
        kb = [
            [
                InlineKeyboardButton("🔗 Kanal qo‘shish", callback_data='set_required_channel'),
                InlineKeyboardButton("❌ Kanal o‘chirish", callback_data='remove_required_channel')
            ],
            [
                InlineKeyboardButton("👤 Admin qo‘shish", callback_data='add_admin'),
                InlineKeyboardButton("👤 Admin o‘chirish", callback_data='remove_admin')
            ],
            [
                InlineKeyboardButton("📊 Statistika", callback_data='statistics')
            ],
            [InlineKeyboardButton("🔙 Bosh menyuga", callback_data='back_to_main')]
        ]
        await q.edit_message_text(
            "<b>👑 Admin panel</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if q.data == 'set_required_channel' and is_admin_user:
        kb = [
            [
                InlineKeyboardButton("📢 Oddiy channel", callback_data='add_normal_channel'),
                InlineKeyboardButton("🔐 Request channel", callback_data='add_request_channel')
            ],
            [InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]
        ]
        await q.edit_message_text(
            "<b>Qanday turdagi kanal qo'shmoqchisiz?</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if q.data == 'add_normal_channel' and is_admin_user:
        context.user_data["awaiting_required_channel"] = True
        context.user_data["channel_type"] = "normal"
        await q.edit_message_text(
            "<b>🔗 Majburiy kanal username ni yuboring</b>\n\n"
            "Faqat @ bilan boshlanadigan shaklda:\n"
            "Misol: @kinolar_kanali\n\n",
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        return

    if q.data == 'add_request_channel' and is_admin_user:
        context.user_data["awaiting_required_channel"] = True
        context.user_data["channel_type"] = "request_forward"
        await q.edit_message_text(
            "<b>1-qadam: 📨 Request kanaldan bitta MATNLI (Text) postni shu botga uzatib yuboring (forward qiling).</b>\n\n"
            "<i>(Bu orqali bot kanal ID sini bilib a'zolikni aniq tekshira oladi. Eslatma: Bot o'sha Request kanalda albatta admin bo'lishi shart!)</i>",
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        return

    if q.data == 'remove_required_channel' and is_admin_user:
        channels = get_required_channels()
        if not channels:
            await q.edit_message_text(
                "<b>❌ Hozircha hech qanday majburiy kanal yo'q.</b>",
                parse_mode="HTML",
                reply_markup=admin_back_button()
            )
            return

        kb = []
        for i, ch in enumerate(channels):
            if '|' in ch:
                name = f"Request Kanal {i+1} (ID:{ch.split('|')[0][:6]}...)"
            else:
                name = ch[1:] if ch.startswith('@') else f"Request Kanal {i+1}"
            kb.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"rem_chan_{i}")])

        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')])

        await q.edit_message_text(
            "<b>❌ Qaysi kanalni o‘chirishni xohlaysiz?</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if q.data.startswith('rem_chan_') and is_admin_user:
        idx = int(q.data.replace('rem_chan_', ''))
        channels = get_required_channels()
        if idx < len(channels):
            channel = channels[idx]
            remove_required_channel(channel)
            await q.edit_message_text(
                f"<b>✅ Kanal o‘chirildi:</b> {channel}",
                parse_mode="HTML",
                reply_markup=admin_back_button()
            )
        return

    if q.data == 'add_admin' and is_admin_user:
        context.user_data["awaiting_add_admin"] = True
        await q.edit_message_text(
            "<b>👤 Yangi admin Telegram ID'sini yuboring</b>\n\n"
            "Masalan: 123456789\n\n",
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        return

    if q.data == 'remove_admin' and is_admin_user:
        admins = get_admins()
        if len(admins) <= 1:
            await q.edit_message_text(
                "<b>❌ Hozircha faqat asosiy admin bor.</b>",
                parse_mode="HTML",
                reply_markup=admin_back_button()
            )
            return

        kb = []
        for aid in admins:
            if aid == MAIN_ADMIN_ID:
                continue
            kb.append([InlineKeyboardButton(f"❌ ID: {aid}", callback_data=f"remove_admin_id_{aid}")])

        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')])

        await q.edit_message_text(
            "<b>👤 Qaysi adminni o‘chirishni xohlaysiz?</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if q.data.startswith('remove_admin_id_') and is_admin_user:
        admin_id = int(q.data.replace('remove_admin_id_', ''))
        remove_admin(admin_id)
        await q.edit_message_text(
            f"<b>✅ Admin o‘chirildi:</b> {admin_id}",
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        return

    if q.data == 'search':
        await q.edit_message_text(
            "<b>🔍 Kino nomi yoki kodini yozing:</b>",
            parse_mode="HTML",
            reply_markup=back_button()
        )
        return

    if q.data == 'top_movies':
        if not data.get("movies"):
            text = "Hozircha filmlar yo‘q 😔"
        else:
            top = sorted(
                data["movies"].items(),
                key=lambda x: float(x[1].get("rating", "0") or 0),
                reverse=True
            )[:8]
            text = "<b>🏆 Eng yuqori reytingli filmlar:</b>\n\n"
            for code, m in top:
                text += f"• <b>{m['name']}</b> ({code}) | Reyting: {m.get('rating', '—')}⭐️\n"
        await q.edit_message_text(text, parse_mode="HTML", reply_markup=back_button())
        return

    if q.data == 'info':
        await q.edit_message_text(
            "<b>✨ Bot haqida qisqacha:</b>\n\n"
            "🎬 <b>Kod</b> yozsangiz — darhol video chiqadi\n"
            "🔎 <b>Nom</b> yozsangiz — qidiruv natijalari\n"
            "🏆 <b>Top filmlar</b> — reyting bo‘yicha eng zo‘r filmlar\n\n"
            "Admin bilan bog‘lanish: @admin_username",
            parse_mode="HTML",
            reply_markup=back_button()
        )
        return

    if q.data == 'admin_panel' and is_admin_user:
        kb = [
            [
                InlineKeyboardButton("🔗 Kanal qo‘shish", callback_data='set_required_channel'),
                InlineKeyboardButton("❌ Kanal o‘chirish", callback_data='remove_required_channel')
            ],
            [
                InlineKeyboardButton("👤 Admin qo‘shish", callback_data='add_admin'),
                InlineKeyboardButton("👤 Admin o‘chirish", callback_data='remove_admin')
            ],
            [
                InlineKeyboardButton("📊 Statistika", callback_data='statistics')
            ],
            [InlineKeyboardButton("🔙 Bosh menyuga", callback_data='back_to_main')]
        ]
        await q.edit_message_text(
            "<b>👑 Admin panel</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if q.data == 'statistics' and is_admin_user:
        users = data.get("users", {})
        movies = data.get("movies", {})
        channels = get_required_channels()

        users_count = len(users)
        movies_count = len(movies)
        channels_count = len(channels)

        # Bugungi yangi foydalanuvchilar
        today = datetime.now().strftime("%Y-%m-%d")
        new_today = sum(
            1 for u in users.values()
            if isinstance(u, dict) and u.get("joined", "").startswith(today)
        )

        # Blok qilingan foydalanuvchilar
        now_ts = datetime.now().timestamp()
        blocked_count = sum(
            1 for u in users.values()
            if isinstance(u, dict) and u.get("block_until", 0) > now_ts
        )

        # Eng so'ngi qo'shilgan film
        if movies:
            try:
                last_movie = max(
                    movies.items(),
                    key=lambda x: x[1].get("added", "")
                )
                last_movie_text = f"<b>{last_movie[1]['name']}</b> ({last_movie[0]})"
            except Exception:
                last_movie_text = "—"
        else:
            last_movie_text = "—"


        # Required channels turi
        normal_ch = sum(1 for c in channels if not '|' in c and not c.startswith('http'))
        request_ch = sum(1 for c in channels if '|' in c)

        stat_text = (
            "<b>📊 Bot Statistikasi</b>\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"👥 <b>Foydalanuvchilar:</b> {users_count} ta\n"
            f"🆕 <b>Bugun qo'shildi:</b> {new_today} ta\n"
            f"⛔️ <b>Blok qilingan:</b> {blocked_count} ta\n\n"
            f"🎬 <b>Jami filmlar:</b> {movies_count} ta\n"
            f"🕐 <b>Oxirgi film:</b> {last_movie_text}\n"
            f"📢 <b>Kanallar:</b> {channels_count} ta\n"
            f"   • Oddiy: {normal_ch} ta\n"
            f"   • Request: {request_ch} ta\n\n"
            f"🗓 <b>Sana:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        stat_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Kino o'chirish", callback_data='delete_movie')],
            [InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]
        ])
        await q.edit_message_text(
            stat_text,
            parse_mode="HTML",
            reply_markup=stat_kb
        )
        return

    if q.data == 'delete_movie' and is_admin_user:
        return await show_delete_movie_list(update, context, data, is_admin_user, page=0)

    if q.data.startswith('del_page_') and is_admin_user:
        page = int(q.data.replace('del_page_', ''))
        return await show_delete_movie_list(update, context, data, is_admin_user, page=page)

    if q.data.startswith('confirm_del_') and is_admin_user:
        # Kodda tag chiziq bo'lishi mumkinligini hisobga olib, oxirgi qismini emas, 
        # 'confirm_del_' dan keyingi hamma qismini olamiz
        code = q.data[12:] 
        movie_info = data.get("movies", {}).get(code)
        
        if movie_info:
            name = movie_info.get("name", "—")
            del data["movies"][code]
            save_data(data)
            
            await q.answer(f"✅ {name} o'chirildi!", show_alert=True)
            
            # Joriy sahifani aniqlash (oddiyroq bo'lishi uchun 0-sahifaga qaytarish 
            # yoki joriy holatni saqlash mumkin, hozircha 0)
            return await show_delete_movie_list(update, context, data, is_admin_user, page=0)
        else:
            await q.answer("❌ Bu kino topilmadi", show_alert=True)
        return

async def show_delete_movie_list(update, context, data, is_admin_user, page=0):
    q = update.callback_query
    movies = data.get("movies", {})
    if not movies:
        await q.edit_message_text(
            "<b>❌ Hozircha kinolar yo'q.</b>",
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        return

    # Kinolarni kodlari bo'yicha tartiblash (raqam bo'lsa raqamdek, bo'lmasa matndek)
    all_movies = sorted(
        movies.items(),
        key=lambda x: (int(x[0]) if x[0].isdigit() else 999999, x[0])
    )

    per_page = 10
    total_pages = (len(all_movies) + per_page - 1) // per_page
    
    if page >= total_pages: page = total_pages - 1
    if page < 0: page = 0

    start_idx = page * per_page
    end_idx = start_idx + per_page
    current_page_movies = all_movies[start_idx:end_idx]

    kb = []
    # Faqat kino kodi va nomi (tartib raqamisiz)
    for code, m in current_page_movies:
        kb.append([InlineKeyboardButton(f"🗑 {code} - {m['name'][:25]}", callback_data=f"confirm_del_{code}")])

    # Pagination tugmalari
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"del_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="none"))
    
    if (page + 1) < total_pages:
        nav_buttons.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"del_page_{page+1}"))
    
    if nav_buttons:
        kb.append(nav_buttons)

    kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data='statistics')])

    text = (
        "<b>🗑 O'chirish uchun kinoni tanlang:</b>\n\n"
        f"Jami filmlar: {len(all_movies)} ta"
    )

    await q.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )




    if q.data == 'cancel_add':
        context.user_data.clear()
        await q.edit_message_text("Amal bekor qilindi", reply_markup=main_keyboard(is_admin_user))
        return

    if q.data.startswith('play_'):
        code = q.data.replace('play_', '')
        if code not in data.get("movies", {}):
            await q.message.reply_text("Bunday kod topilmadi")
            return
        m = data["movies"][code]

        caption = (
            f"🎬 <b>{m['name']}</b>\n"
            f"🆔<b>Kod:</b> {code}"
        )
        if "description" in m and m["description"]:
            caption += f"\n\n{m['description']}"

        try:
            await q.message.reply_sticker(FILM_STICKER_ID)
        except:
            pass

        if "file_id" in m:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌", callback_data='delete_msg')]
            ])
            await q.message.reply_video(
                video=m["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            await q.message.reply_text(caption + "\n\nVideoni botda topa olmadim.", parse_mode="HTML")
        return

# ===== TEXT HANDLER (LIMIT QO'SHILGAN) =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = load_data()
    uid = str(update.effective_user.id)
    is_admin_user = check_is_admin(update.effective_user.id)
    required_channels = get_required_channels()

    unsubscribed = await get_unsubscribed_channels(context, update.effective_user.id, is_admin_user, required_channels)
    if unsubscribed:
        await show_subscription_prompt(update, context, unsubscribed)
        return

    if context.user_data.get("awaiting_required_channel") and is_admin_user:
        if text.lower() in ["/cancel", "bekor", "orqaga"]:
            context.user_data.clear()
            await update.message.reply_text("Bekor qilindi.", reply_markup=admin_back_button())
            return

        channel = text.strip()
        channel_type = context.user_data.get("channel_type", "normal")

        if channel_type == "request_forward":
            chat = None
            if hasattr(update.message, "forward_origin") and getattr(update.message.forward_origin, "type", "") in ("chat", "channel"):
                chat = getattr(update.message.forward_origin, "chat", None)
            elif getattr(update.message, "forward_from_chat", None):
                chat = update.message.forward_from_chat
                
            if not chat:
                await update.message.reply_text("Iltimos, kanaldan xabarni forward qiling!\n"
                                             "(Xabar kanaldan olingan bo'lishi shart)")
                return
                
            context.user_data["temp_chat_id"] = str(chat.id)
            context.user_data["channel_type"] = "request_link"
            await update.message.reply_text(
                "<b>2-qadam: 🔗 Endi Request kanal ssilkasini yuboring</b>\n\n"
                "Misol: https://t.me/+IDHbtcaJfIA4ZjJi\n\n",
                parse_mode="HTML",
                reply_markup=admin_back_button()
            )
            return

        elif channel_type == "request_link":
            if not text.startswith('http'):
                await update.message.reply_text("Ssilka https://t.me/ bilan boshlanishi kerak!")
                return
            chat_id = context.user_data.get("temp_chat_id")
            channel = f"{chat_id}|{text.strip()}"
            add_required_channel(channel)
            context.user_data.clear()
            await update.message.reply_text(
                f"<b>✅ Majburiy request kanal qo‘shildi!</b>",
                parse_mode="HTML",
                reply_markup=admin_back_button()
            )
            return

        elif channel_type == "normal" and not channel.startswith('@'):
            await update.message.reply_text("Faqat @username shaklida yuboring!")
            return

        if channel_type == "normal":
            add_required_channel(channel)
            context.user_data.clear()
            await update.message.reply_text(
                f"<b>✅ Majburiy kanal qo‘shildi:</b> {channel}",
                parse_mode="HTML",
                reply_markup=admin_back_button()
            )
        return

    # Deleting movie mode is now handled exclusively via buttons in show_delete_movie_list
    if context.user_data.get("deleting_movie") and is_admin_user:
        if text.lower() in ["/cancel", "bekor", "orqaga"]:
            context.user_data.clear()
            await update.message.reply_text("Bekor qilindi", reply_markup=main_keyboard(is_admin_user))
            return

        code = text.strip().upper()
        if code in data.get("movies", {}):
            name = data["movies"][code].get("name", "—")
            del data["movies"][code]
            save_data(data)
            kb = [
                [InlineKeyboardButton("🗑 Yana o'chirish", callback_data='delete_movie')],
                [InlineKeyboardButton("🔙 Admin panel", callback_data='back_to_admin_panel')]
            ]
            await update.message.reply_text(
                f"<b>✅ Muvaffaqiyatli o'chirildi!</b>\n🆔 Kod: <code>{code}</code>\n🎬 Nomi: {name}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await update.message.reply_text(
                f"❌ <b>{code}</b> kodi topilmadi!\nQayta kiring yoki /cancel bilan bekor qiling.",
                parse_mode="HTML"
            )
            return
        context.user_data.clear()
        return

    if context.user_data.get("awaiting_add_admin") and is_admin_user:
        if text.lower() in ["/cancel", "bekor", "orqaga"]:
            context.user_data.clear()
            await update.message.reply_text("Bekor qilindi.", reply_markup=admin_back_button())
            return

        try:
            new_admin_id = int(text.strip())
            if add_admin(new_admin_id):
                context.user_data.clear()
                await update.message.reply_text(
                    f"<b>✅ Yangi admin qo‘shildi:</b> {new_admin_id}",
                    parse_mode="HTML",
                    reply_markup=admin_back_button()
                )
            else:
                await update.message.reply_text("Bu ID allaqachon admin yoki noto‘g‘ri!", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("Iltimos, faqat raqam yuboring (Telegram ID)", parse_mode="HTML")
        return

    # ===== LIMIT TEKSHIRUV =====
    if not is_admin_user:
        if uid not in data["users"]:
            data["users"][uid] = {
                "name": update.effective_user.first_name,
                "username": update.effective_user.username or "",
                "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "code_attempts": 0,
                "block_until": 0
            }

        user_info = data["users"][uid]
        current_time = datetime.now().timestamp()

        # Blok tekshirish
        if current_time < user_info.get("block_until", 0):
            remaining = int(user_info["block_until"] - current_time)
            minutes = remaining // 60
            seconds = remaining % 60
            await update.message.reply_text(
                f"⛔️ Siz limitdan oshib ketdingiz!\n\n"
                f"Yana {minutes} daqiqa {seconds} soniya kutishingiz kerak."
            )
            return

        # Kod yozilganda limitni oshirish (Aniq kod yoki nomdagi qanaqadir matn)
        is_valid_code = (
            text.upper() in data.get("movies", {}) or
            any(text.lower() in m["name"].lower() for c, m in data.get("movies", {}).items())
        )

        if is_valid_code:
            user_info["code_attempts"] += 1
            if user_info["code_attempts"] >= MAX_CODE_ATTEMPTS:
                user_info["block_until"] = current_time + (BLOCK_DURATION_MINUTES * 60)
                user_info["code_attempts"] = 0
                save_data(data)
                await update.message.reply_text(
                    f"❌ Siz 10 ta kod limitini to'ldirdingiz!\n"
                    f"15 daqiqadan so'ng qayta urinib ko'rishingiz mumkin."
                )
                return

    # ===== KOD / QIDIRUV LOGIKASI (Faqat admin rejimda bo'lmasa) =====
    if context.user_data:
        # Agar biron rejimda bo'lsa va yuqoridagilarga tushmagan bo'lsa, qidiruvni cheklaymiz
        return

    code = text.upper()
    if code in data.get("movies", {}):
        m = data["movies"][code]
        caption = (
            f"🎬 <b>{m['name']}</b>\n"
            f"🆔<b>Kod:</b> {code}"
        )
        if "description" in m and m["description"]:
            caption += f"\n\n{m['description']}"

        try:
            await update.message.reply_sticker(FILM_STICKER_ID)
        except:
            pass

        if "file_id" in m:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌", callback_data='delete_msg')]
            ])
            await update.message.reply_video(
                video=m["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            await update.message.reply_text(caption + "\n\nVideoni botda topa olmadim.", parse_mode="HTML")
        save_data(data)
        return

    if text.isdigit():
        # Agar faqat raqam bo'lsa, qisman qidiruv qilmaymiz (aniq kod yuqorida tekshirildi)
        found = []
    else:
        # Agar matn bo'lsa, nomlar ichidan qidiramiz
        found = [
            (c, m) for c, m in data.get("movies", {}).items()
            if text.lower() in m["name"].lower()
        ]

    if not found:
        await update.message.reply_text("Hech narsa topilmadi 😔")
        return

    if len(found) == 1:
        c, m = found[0]
        caption = (
            f"🎬 <b>{m['name']}</b>\n"
            f"🆔<b>Kod:</b> {c}"
        )
        if "description" in m and m["description"]:
            caption += f"\n\n{m['description']}"

        try:
            await update.message.reply_sticker(FILM_STICKER_ID)
        except:
            pass

        if "file_id" in m:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌", callback_data='delete_msg')]
            ])
            await update.message.reply_video(
                video=m["file_id"],
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            await update.message.reply_text(caption + "\n\nVideoni botda topa olmadim.", parse_mode="HTML")
        save_data(data)
        return

    buttons = []
    for c, m in found[:10]:
        buttons.append([InlineKeyboardButton(f"{c} – {m['name'][:28]}", callback_data=f"play_{c}")])

    await update.message.reply_text(
        f"<b>Topildi: {len(found)} ta film</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    save_data(data)  # Limit o'zgargan bo'lsa saqlaymiz

# ===== ADD MOVIE =====
async def handle_forwarded_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MAIN_ADMIN_ID or not context.user_data.get("adding_movie"):
        return

    msg = update.message
    if not msg.video or not msg.caption:
        await msg.reply_text("Video va caption kerak!")
        return

    info = {}
    for line in msg.caption.splitlines():
        line = line.strip()
        if ':' in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            info[k] = v

    if "Kod" not in info or "Nom" not in info:
        await msg.reply_text("Captionda <b>Kod</b> va <b>Nom</b> bo‘lishi shart!", parse_mode="HTML")
        return

    code = info["Kod"].upper()
    data = load_data()

    if code in data.get("movies", {}):
        await msg.reply_text(f"<b>{code}</b> allaqachon mavjud!", parse_mode="HTML")
        return

    data["movies"][code] = {
        "name": info["Nom"],
        "rating": info.get("Reyting", "—"),
        "genre": info.get("Janr", "—"),
        "description": info.get("Tavsif", ""),
        "file_id": msg.video.file_id,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(data)
    context.user_data.clear()

    kb = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]]

    await msg.reply_text(
        f"🎉 <b>Muvaffaqiyatli qo‘shildi!</b>\n"
        f"<b>{info['Nom']}</b> – {code}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ===== KANAL VIDEO HANDLER =====
async def handle_channel_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kanalda video post qilinganda caption'da 'Nom:' tegi bo'lsa,
    bot avtomatik raqamli kod yaratib, filmni saqlaydi.
    Agar 'Kod:' ham bo'lsa, o'sha kod ishlatiladi.
    """
    msg = update.channel_post
    if not msg or not msg.video:
        return

    caption = msg.caption or ""
    info = {}
    for line in caption.splitlines():
        line = line.strip()
        if ':' in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            info[k] = v

    # Faqat "Nom:" tegi bo'lsa ishlaydi
    if "Nom" not in info:
        return

    data = load_data()

    # Kod: yozilgan bo'lsa o'shani ishlat, aks holda avtomatik raqam
    if "Kod" in info and info["Kod"].strip():
        code = info["Kod"].strip().upper()
    else:
        existing_codes = [k for k in data.get("movies", {}).keys() if k.isdigit()]
        next_num = (max(int(c) for c in existing_codes) + 1) if existing_codes else 1
        code = str(next_num)

    # Agar kod allaqachon mavjud bo'lsa, yangi raqam tayinla
    if code in data.get("movies", {}):
        existing_codes = [k for k in data.get("movies", {}).keys() if k.isdigit()]
        next_num = (max(int(c) for c in existing_codes) + 1) if existing_codes else 1
        code = str(next_num)

    data["movies"][code] = {
        "name": info["Nom"],
        "rating": info.get("Reyting", "—"),
        "genre": info.get("Janr", "—"),
        "description": info.get("Tavsif", ""),
        "file_id": msg.video.file_id,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_data(data)

    try:
        await context.bot.send_message(
            chat_id=MAIN_ADMIN_ID,
            text=(
                f"✅ <b>Yangi film avtomatik qo'shildi!</b>\n\n"
                f"🎬 Nom: <b>{info['Nom']}</b>\n"
                f"🆔 Kod: <b>{code}</b>\n"
                f"⭐️ Reyting: {info.get('Reyting', '—')}\n"
                f"🎭 Janr: {info.get('Janr', '—')}"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Admin xabar yuborishda xato: {e}")

# ===== JOIN REQUEST HANDLER =====
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = str(update.effective_user.id)
        chat_id = str(update.chat_join_request.chat.id)
        
        data = load_data()
        if "requests" not in data:
            data["requests"] = {}
        if chat_id not in data["requests"]:
            data["requests"][chat_id] = []
            
        if user_id not in data["requests"][chat_id]:
            data["requests"][chat_id].append(user_id)
            save_data(data)
            
    except Exception as e:
        logger.error(f"Join request error: {e}")

# ===== MAIN =====
def main():
    import keep_alive
    keep_alive.keep_alive()

    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Kanal video handler - kanaldan video kelganda avtomatik saqlaydi
    app.add_handler(MessageHandler(filters.VIDEO & filters.UpdateType.CHANNEL_POSTS, handle_channel_video))

    print("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

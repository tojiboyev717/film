import os
import json
import logging
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
TOKEN = "7692358431:AAGvQd0H9QVcfApimKW1DFmOmupe98qEMwg"
MAIN_ADMIN_ID = 6560139113
DATA_FILE = "kino.txt"
CHANNEL_FILE = "channels.txt"
ADMINS_FILE = "admins.txt"

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
    if not os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'w') as f:
            f.write(f"{MAIN_ADMIN_ID}\n")
        return [MAIN_ADMIN_ID]
    try:
        with open(ADMINS_FILE, 'r') as f:
            return [int(line.strip()) for line in f if line.strip().isdigit()]
    except:
        return [MAIN_ADMIN_ID]

def check_is_admin(user_id):
    return user_id in get_admins()

def add_admin(admin_id):
    if admin_id == MAIN_ADMIN_ID:
        return False
    admins = get_admins()
    if admin_id not in admins:
        with open(ADMINS_FILE, 'a') as f:
            f.write(f"{admin_id}\n")
        return True
    return False

def remove_admin(admin_id):
    if admin_id == MAIN_ADMIN_ID:
        return False
    admins = get_admins()
    if admin_id in admins:
        admins.remove(admin_id)
        with open(ADMINS_FILE, 'w') as f:
            for aid in admins:
                f.write(f"{aid}\n")
        return True
    return False

# ===== DATA =====
def load_data():
    default = {
        "movies": {},
        "users": {},
        "channel_link": "https://t.me/+FQ3XcZl0VUM4NTgy",
        "requests": {}
    }
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("users", {})
            data.setdefault("movies", {})
            data.setdefault("requests", {})
            for uid, info in data["users"].items():
                info.setdefault("code_attempts", 0)
                info.setdefault("block_until", 0)
            return data
    except Exception as e:
        logger.error(f"Data yuklash xatosi: {e}")
        return default

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Data saqlash xatosi: {e}")

# ===== KANAL =====
def get_required_channels():
    if not os.path.exists(CHANNEL_FILE):
        return []
    try:
        with open(CHANNEL_FILE, 'r', encoding='utf-8') as f:
            lines = []
            for line in f:
                line = line.strip()
                if line.startswith('@') or line.startswith('http') or '|' in line:
                    lines.append(line)
            return lines
    except:
        return []

def add_required_channel(channel):
    if not (channel.startswith('@') or channel.startswith('http') or '|' in channel):
        return False
    try:
        with open(CHANNEL_FILE, 'a', encoding='utf-8') as f:
            f.write(channel.strip() + '\n')
        return True
    except:
        return False

def remove_required_channel(channel):
    channels = get_required_channels()
    if channel in channels:
        channels.remove(channel)
        try:
            with open(CHANNEL_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(channels) + '\n')
            return True
        except:
            return False
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
                InlineKeyboardButton("➕ Yangi film qo‘shish", callback_data='add_movie'),
                InlineKeyboardButton("🗑 Film o‘chirish", callback_data='delete_movie')
            ],
            [
                InlineKeyboardButton("🔗 Kanal qo‘shish", callback_data='set_required_channel'),
                InlineKeyboardButton("❌ Kanal o‘chirish", callback_data='remove_required_channel')
            ],
            [
                InlineKeyboardButton("👤 Admin qo‘shish", callback_data='add_admin'),
                InlineKeyboardButton("👤 Admin o‘chirish", callback_data='remove_admin')
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
                InlineKeyboardButton("➕ Yangi film qo‘shish", callback_data='add_movie'),
                InlineKeyboardButton("🗑 Film o‘chirish", callback_data='delete_movie')
            ],
            [
                InlineKeyboardButton("🔗 Kanal qo‘shish", callback_data='set_required_channel'),
                InlineKeyboardButton("❌ Kanal o‘chirish", callback_data='remove_required_channel')
            ],
            [
                InlineKeyboardButton("👤 Admin qo‘shish", callback_data='add_admin'),
                InlineKeyboardButton("👤 Admin o‘chirish", callback_data='remove_admin')
            ],
            [InlineKeyboardButton("🔙 Bosh menyuga", callback_data='back_to_main')]
        ]
        await q.edit_message_text(
            "<b>👑 Admin panel</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if q.data == 'add_movie' and is_admin_user:
        context.user_data["adding_movie"] = True
        await q.edit_message_text(
            "<b>🎥 Videoni forward qiling!</b>\n\n"
            "Captionda quyidagilar bo‘lishi kerak:\n"
            "Kod: ABC123\n"
            "Nom: ...\n"
            "Reyting: ...\n"
            "Janr: ...\n"
            "Tavsif: ...",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]])
        )
        return

    if q.data == 'delete_movie' and is_admin_user:
        context.user_data["deleting_movie"] = True
        await q.edit_message_text(
            "<b>🗑 O'chiriladigan filmning kodini yozing</b>\n\n"
            "Masalan: ABC123",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]])
        )
        return

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
            f"🆔<b>Kod:</b> {code}\n"
            f"⭐<b>Reyting:</b> {m.get('rating', '—')}\n"
            f"🎭<b>Janr:</b> {m.get('genre', '—')}"
        )
        if "description" in m and m["description"]:
            caption += f"\n\n{m['description']}"

        try:
            await q.message.reply_sticker(FILM_STICKER_ID)
        except:
            pass

        if "file_id" in m:
            await q.message.reply_video(
                video=m["file_id"],
                caption=caption,
                parse_mode="HTML"
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
            kb = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_admin_panel')]]
            await update.message.reply_text(
                f"<b>✅ Muvaffaqiyatli o‘chirildi!</b>\nKod: {code}\nNomi: {name}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await update.message.reply_text(f"<b>{code}</b> topilmadi", parse_mode="HTML")
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

        # Kod yozilganda limitni oshirish
        is_valid_code = (
            text.upper() in data.get("movies", {}) or
            any(text.lower() in c.lower() or text.lower() in m["name"].lower() for c, m in data.get("movies", {}).items())
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

    # ===== KOD / QIDIRUV LOGIKASI =====
    code = text.upper()
    if code in data.get("movies", {}):
        m = data["movies"][code]
        caption = (
            f"🎬 <b>{m['name']}</b>\n"
            f"🆔<b>Kod:</b> {code}\n"
            f"⭐<b>Reyting:</b> {m.get('rating', '—')}\n"
            f"🎭<b>Janr:</b> {m.get('genre', '—')}"
        )
        if "description" in m and m["description"]:
            caption += f"\n\n{m['description']}"

        try:
            await update.message.reply_sticker(FILM_STICKER_ID)
        except:
            pass

        if "file_id" in m:
            await update.message.reply_video(
                video=m["file_id"],
                caption=caption,
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(caption + "\n\nVideoni botda topa olmadim.", parse_mode="HTML")
        save_data(data)
        return

    found = [
        (c, m) for c, m in data.get("movies", {}).items()
        if text.lower() in c.lower() or text.lower() in m["name"].lower()
    ]

    if not found:
        await update.message.reply_text("Hech narsa topilmadi 😔")
        return

    if len(found) == 1:
        c, m = found[0]
        caption = (
            f"🎬 <b>{m['name']}</b>\n"
            f"🆔<b>Kod:</b> {c}\n"
            f"⭐<b>Reyting:</b> {m.get('rating', '—')}\n"
            f"🎭<b>Janr:</b> {m.get('genre', '—')}"
        )
        if "description" in m and m["description"]:
            caption += f"\n\n{m['description']}"

        try:
            await update.message.reply_sticker(FILM_STICKER_ID)
        except:
            pass

        if "file_id" in m:
            await update.message.reply_video(
                video=m["file_id"],
                caption=caption,
                parse_mode="HTML"
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

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(
        MessageHandler(filters.VIDEO & filters.User(user_id=MAIN_ADMIN_ID), handle_forwarded_video)
    )

    print("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
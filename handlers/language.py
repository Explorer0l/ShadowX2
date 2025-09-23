"""
Language handler module for ShadowX Bot
Handles language selection and text localization
"""

from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from aiogram.filters import Command
from database import update_user_language, get_user
from config import UNIVERSITIES, ADMIN_ID, is_admin
import state

# Language dictionaries
TEXTS = {
    "ru": {
        "welcome": "👋 Привет! Я — анонимный чат бот для студентов.",
        "disclaimer": "❗️ ВАЖНОЕ УВЕДОМЛЕНИЕ ❗️\n\nОснователь бота не несет никакой ответственности за пользователей. "
                     "Каждый пользователь берет ответственность за себя и свои действия в боте.\n\n"
                     "Нажимая кнопку '✅ Подтвердить', вы соглашаетесь с этим условием.",
        "confirm": "✅ Подтвердить",
        "intro": "✨ Как это работает:\n"
                 "1️⃣ Выбери свой университет\n"
                 "2️⃣ Укажи тип сообщения\n"
                 "3️⃣ Напиши текст — я проверю его и опубликую\n\n"
                 "📢 Все сообщения проверяются администратором\n",
        "rules": "❗️❗️❗️ПРАВИЛА❗️❗️❗️\n"
                "• Сообщения с матами и рекламой требуют одобрения\n"
                "• Смена университета — через админа\n"
                "• Контент 18+(🔞) = бан\n\n",
        "select_university": "Выбери вуз: 👇",
        "select_message_type": "Выбери тип сообщения:",
        "suggest_idea": "💡Предложить идею",
        "write_idea": "✍️ Напишите вашу идею или пришлите медиа (фото/видео).",
        "idea_received": "✅ Идея отправлена администратору",
        "university_selected": "✅ Выбран {}",
        "university_changed": "✅ Университет изменен на {}",
        "write_message": "✍️ Напишите ваше сообщение (текст, фото или видео):\n\n"
                        "ℹ️ Сообщения проверяются автоматически:\n"
                        "- Фото/видео ➡️ всегда требуют одобрения\n"
                        "- Маты ➡️ отправляются администратору на проверку\n"
                        "- Остальные сообщения ➡️ проходят проверку",
        "change_university_request": "📩 Ваш запрос отправлен администратору. "
                                   "Свяжитесь с администратором {} и ожидайте решения в течение 24 часов.",
        "university_first": "❌ Сначала выбери университет",
        "message_type_first": "❌ Сначала выбери тип сообщения",
        "message_moderation": "🕒 Твое сообщение отправлено на проверку",
        "media_moderation": "🕒 Твое медиа отправлено на проверку",
        "message_published": "✅ Сообщение опубликовано! (№{number})",
        "media_published": "✅ Твое медиа опубликовано! (№{number})",
        "message_rejected": "❌ Твое сообщение отклонено администратором",
        "media_rejected": "❌ Твое медиа отклонено администратором",
        "message_queued": "🕒 Сообщение поставлено в очередь на публикацию",
        "media_queued": "🕒 Медиа поставлено в очередь на публикацию",
        "error": "❌ Произошла ошибка",
        "when_processing_media": "при обработке медиа",
        "main_menu": "🎓Главное меню🎓",
        "back": "⬅️Назад⬅️",
        "message_types": {
            "help": "🆘Поддержка🆘",
            "confession": "💞Признание💞",
            "regular": "📩Обычное сообщение📩"
        },
        "admin_commands": {
            "admin_panel": "🛠Панель админа",
            "check_queue": "👁Проверить очередь",
            "add_moderator": "➕Добавить модератора",
            "remove_moderator": "➖Убрать модератора",
            "list_moderators": "👥Список модераторов",
            "rename_moderator": "✏️Переименовать модератора",
            "back_main": "⬅️ В главное меню"
        },
        "moderator_commands": {
            "moderator_panel": "🛡Панель модератора",
            "check_queue": "👁Проверить очередь",
            "back_main": "⬅️ В главное меню"
        },
        "menu": {
            "admin_title": "🛠 Панель администратора",
            "moderator_title": "🛡 Панель модератора"
        },
        "prompts": {
            "enter_mod_id_add": "Отправьте ID пользователя модератора (число):",
            "enter_mod_name": "Отправьте имя модератора:",
            "enter_mod_id_remove": "Отправьте ID модератора для удаления:",
            "enter_mod_id_rename": "Отправьте ID модератора для изменения имени:",
            "enter_new_name": "Отправьте новое имя модератора:",
            "numeric_id": "Пожалуйста, отправьте числовой ID.",
            "min_words": "Минимальная длина сообщения — 4 слов. Пожалуйста, расширьте текст."
        },
        "result": {
            "mod_added": "Модератор добавлен: {id} — {name}",
            "mod_removed": "Модератор удален: {id}",
            "mod_not_found": "Пользователь не является модератором.",
            "mod_renamed": "Имя модератора обновлено: {id} — {name}",
            "cannot_remove_admin": "Нельзя удалить владельца-админа.",
            "queue_empty": "ℹ️ Очередь модерации пуста"
        },
        "moderator_actions": {
            "message_approved": "✅ Модератор {moderator} одобрил сообщение #{message_id} от пользователя {user_id}:\n\n📝 {content}",
            "message_rejected": "❌ Модератор {moderator} отклонил сообщение #{message_id} от пользователя {user_id}:\n\n📝 {content}",
            "media_approved": "✅ Модератор {moderator} одобрил медиа #{message_id} от пользователя {user_id}:\n\n📝 {caption}",
            "media_rejected": "❌ Модератор {moderator} отклонил медиа #{message_id} от пользователя {user_id}:\n\n📝 {caption}",
            "university_change_approved": "✅ Модератор {moderator} одобрил смену университета для пользователя {user_id}",
            "university_change_rejected": "❌ Модератор {moderator} отклонил смену университета для пользователя {user_id}"
        },
        "change_university": "🔄Запросить смену университета🔄",
        "language_selection": "🌐 Выберите язык / Select language:",
        "language_changed": "✅ Язык изменен на русский",
        "start_with_start": "Пожалуйста, начните с команды /start",
        "university_change_approved": "✅ Запрос на смену университета одобрен. Выберите новый университет:",
        "university_change_rejected": "❌ Запрос на смену университета отклонен."
    },
    "en": {
        "welcome": "👋 Hello! I am an anonymous bot for students.",
        "disclaimer": "❗️ IMPORTANT NOTICE ❗️\n\nThe creator of the bot is not responsible for users. "
                     "Each user takes responsibility for themselves and their actions in the bot.\n\n"
                     "By pressing the '✅ Confirm' button, you agree to this condition.",
        "confirm": "✅ Confirm",
        "intro": "✨ How it works:\n"
                 "1️⃣ Choose your university\n"
                 "2️⃣ Select the message type\n"
                 "3️⃣ Write your text — I'll check and publish it\n\n"
                 "📢 All messages are reviewed by the administrator\n",
        "rules": "❗️❗️❗️RULES❗️❗️❗️\n"
                "• Messages with profanity and ads require approval\n"
                "• University change — through admin\n"
                "• Content 18+(🔞) = ban\n\n",
        "select_university": "Choose your university: 👇",
        "select_message_type": "Choose message type:",
        "suggest_idea": "💡Suggest idea",
        "write_idea": "✍️ Send your idea or attach media (photo/video).",
        "idea_received": "✅ Idea sent to admin",
        "university_selected": "✅ Selected {}",
        "university_changed": "✅ University changed to {}",
        "write_message": "✍️ Write your message (text, photo, or video):\n\n"
                        "ℹ️ Messages are checked automatically:\n"
                        "- Photos/videos ➡️ always require approval\n"
                        "- Profanity ➡️ sent to admin for review\n"
                        "- Other messages ➡️ go through review",
        "change_university_request": "📩 Your request has been sent to the administrator. "
                                   "Contact the administrator {} and wait for a decision within 24 hours.",
        "university_first": "❌ First select a university",
        "message_type_first": "❌ First select a message type",
        "message_moderation": "🕒 Your message has been sent for review",
        "media_moderation": "🕒 Your media has been sent for review",
        "message_published": "✅ Message published! (#{number})",
        "media_published": "✅ Your media has been published! (#{number})",
        "message_rejected": "❌ Your message was rejected by the administrator",
        "media_rejected": "❌ Your media was rejected by the administrator",
        "message_queued": "🕒 Your message has been queued for publication",
        "media_queued": "🕒 Your media has been queued for publication",
        "error": "❌ An error occurred",
        "when_processing_media": "while processing media",
        "main_menu": "🎓Main Menu🎓",
        "back": "⬅️Back⬅️",
        "message_types": {
            "help": "🆘Support🆘",
            "confession": "💞Confession💞",
            "regular": "📩Regular message📩"
        },
        "admin_commands": {
            "admin_panel": "🛠Admin panel",
            "check_queue": "👁Check queue",
            "add_moderator": "➕Add moderator",
            "remove_moderator": "➖Remove moderator",
            "list_moderators": "👥Moderators list",
            "rename_moderator": "✏️Rename moderator",
            "back_main": "⬅️ Back to main"
        },
        "moderator_commands": {
            "moderator_panel": "🛡Moderator panel",
            "check_queue": "👁Check queue",
            "back_main": "⬅️ Back to main"
        },
        "menu": {
            "admin_title": "🛠 Admin Panel",
            "moderator_title": "🛡 Moderator Panel"
        },
        "prompts": {
            "enter_mod_id_add": "Send moderator user ID (numeric):",
            "enter_mod_name": "Send moderator name:",
            "enter_mod_id_remove": "Send moderator ID to remove:",
            "enter_mod_id_rename": "Send moderator ID to rename:",
            "enter_new_name": "Send new moderator name:",
            "numeric_id": "Please send a numeric user id.",
            "min_words": "Minimum message length is 4 words. Please provide more details."
        },
        "result": {
            "mod_added": "Moderator added: {id} — {name}",
            "mod_removed": "Moderator removed: {id}",
            "mod_not_found": "User was not a moderator.",
            "mod_renamed": "Moderator name updated: {id} — {name}",
            "cannot_remove_admin": "You cannot remove the owner admin.",
            "queue_empty": "ℹ️ Moderation queue is empty"
        },
        "moderator_actions": {
            "message_approved": "✅ Moderator {moderator} approved message #{message_id} from user {user_id}:\n\n📝 {content}",
            "message_rejected": "❌ Moderator {moderator} rejected message #{message_id} from user {user_id}:\n\n📝 {content}",
            "media_approved": "✅ Moderator {moderator} approved media #{message_id} from user {user_id}:\n\n📝 {caption}",
            "media_rejected": "❌ Moderator {moderator} rejected media #{message_id} from user {user_id}:\n\n📝 {caption}",
            "university_change_approved": "✅ Moderator {moderator} approved university change for user {user_id}",
            "university_change_rejected": "❌ Moderator {moderator} rejected university change for user {user_id}"
        },
        "change_university": "🔄Request university change🔄",
        "language_selection": "🌐 Выберите язык / Select language:",
        "language_changed": "✅ Language changed to English",
        "start_with_start": "Please start with /start",
        "university_change_approved": "✅ University change request approved. Choose a new university:",
        "university_change_rejected": "❌ University change request rejected."
    }
}

def get_text(key, language='ru'):
    """Get localized text based on language and key"""
    lang_dict = TEXTS.get(language, TEXTS["ru"])
    
    # Handle nested keys (with dot notation)
    if "." in key:
        parts = key.split(".")
        current = lang_dict
        for part in parts:
            if part in current:
                current = current[part]
            else:
                return key  # Key not found, return the key itself
        return current
    
    return lang_dict.get(key, key)

# Keyboards
def get_language_keyboard():
    """Get language selection keyboard"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇸 English")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_user_keyboard(user_id, language='ru', is_admin=False, is_moderator=False):
    """Get main keyboard for the user based on language"""
    lang_dict = TEXTS.get(language, TEXTS["ru"]) 
    msg_types = lang_dict["message_types"]
    
    buttons = [
        [KeyboardButton(text=msg_types["help"]), KeyboardButton(text=msg_types["confession"])],
        [KeyboardButton(text=msg_types["regular"]), KeyboardButton(text=get_text("suggest_idea", language))],
        [KeyboardButton(text="🌐 Language/Язык")]
    ]
    
    if is_admin:
        admin_commands = lang_dict["admin_commands"]
        buttons.append([KeyboardButton(text=admin_commands["admin_panel"])])
    elif is_moderator:
        mod_commands = lang_dict.get("moderator_commands", {})
        if mod_commands:
            buttons.append([KeyboardButton(text=mod_commands["moderator_panel"])])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_panel_keyboard(language='ru'):
    """Get admin panel keyboard (localized)."""
    admin_commands = TEXTS.get(language, TEXTS["ru"])["admin_commands"]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=admin_commands["check_queue"])],
            [KeyboardButton(text=admin_commands["add_moderator"])],
            [KeyboardButton(text=admin_commands["remove_moderator"])],
            [KeyboardButton(text=admin_commands["rename_moderator"])],
            [KeyboardButton(text=admin_commands["list_moderators"])],
            [KeyboardButton(text=admin_commands["back_main"])],
        ],
        resize_keyboard=True
    )

def get_moderator_panel_keyboard(language='ru'):
    """Get moderator panel keyboard (localized)."""
    mod_commands = TEXTS.get(language, TEXTS["ru"]).get("moderator_commands", {})
    if not mod_commands:
        mod_commands = TEXTS["ru"]["moderator_commands"]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=mod_commands["check_queue"])],
            [KeyboardButton(text=mod_commands["back_main"])],
        ],
        resize_keyboard=True
    )

def get_university_keyboard(language='ru'):
    """Get university selection keyboard"""
    back_text = get_text("back", language)
    
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=uni)] for uni in UNIVERSITIES] + 
                [[KeyboardButton(text=back_text)]],
        resize_keyboard=True
    )

def get_back_keyboard(language='ru'):
    """Get back button keyboard"""
    back_text = get_text("back", language)
    
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=back_text)]],
        resize_keyboard=True
    )

def get_after_message_keyboard(user_id, language='ru', is_admin=False, is_moderator=False):
    """Get keyboard shown after message submission - returns to main menu"""
    return get_user_keyboard(user_id, language, is_admin=is_admin, is_moderator=is_moderator)

# Language handlers
async def handle_language_selection(message, bot, user_data):
    """Handle language selection"""
    user_id = message.from_user.id
    
    if "🇷🇺" in message.text:
        language = "ru"
        response = get_text("language_changed", "ru")
    else:
        language = "en"
        response = get_text("language_changed", "en")
    
    # Update user's language in database
    update_user_language(user_id, language)
    
    # Update user_data
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]["language"] = language
    
    # Ensure user exists with default university
    user = get_user(user_id)
    try:
        from database import add_user
        from config import UNIVERSITIES
        if (not user) or (not user[2]) or (user[2] not in UNIVERSITIES):
            add_user(user_id, message.from_user.username, 'XIAMEN', language or 'en')
    except Exception:
        logging.debug("Failed to ensure user exists during language selection", exc_info=True)
    
    # Send response with main keyboard
    try:
        from database import is_moderator as _is_moderator
        is_mod = _is_moderator(user_id)
    except Exception:
        is_mod = False
    await message.answer(
        response,
        reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
    )
    
    return language

# Module initialization
async def register_language_handlers(dp, bot):
    """Register language-related handlers"""
    @dp.message(lambda message: message.text in ["🌐 Language/Язык"])
    async def language_command(message: types.Message):
        await message.answer(
            get_text("language_selection", "ru"),
            reply_markup=get_language_keyboard()
        )
    
    @dp.message(lambda message: bool(getattr(message, "text", None)) and ("🇷🇺" in message.text or "🇺🇸" in message.text))
    async def process_language_selection(message: types.Message):
        await handle_language_selection(message, bot, state.user_data)

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

# Language dictionaries (English only)
TEXTS = {
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
            "regular": "📩Regular message📩",
            "confession": "💞Confession💞"
        },
        "admin_commands": {
            "admin_panel": "🛠Admin panel",
            "check_queue": "👁Check queue",
            "ideas_history": "💡Ideas history",
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
        "ideas": {
            "title": "💡 Ideas History",
            "empty": "No ideas yet",
            "page": "Page {page}/{pages} (total: {total})",
            "open": "🔍 Open",
            "prev": "⬅️ Prev",
            "next": "Next ➡️"
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
        "language_selection": "🌐 Select language:",
        "language_changed": "✅ Language set to English",
        "start_with_start": "Please start with /start",
        "university_change_approved": "✅ University change request approved. Choose a new university:",
        "university_change_rejected": "❌ University change request rejected.",
        "result": {
            "queue_empty": "📭 The moderation queue is empty."
        }
    }
}

def get_text(key, language='en'):
    """Get localized text based on language and key (English-only)."""
    lang_dict = TEXTS.get(language, TEXTS["en"])
    
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

def get_user_keyboard(user_id, language='en', is_admin=False, is_moderator=False):
    """Get main keyboard for the user (English-only)"""
    lang_dict = TEXTS.get(language, TEXTS["en"]) 
    msg_types = lang_dict["message_types"]
    
    buttons = [
        [KeyboardButton(text=msg_types["help"]), KeyboardButton(text=msg_types["regular"])],
        [KeyboardButton(text=msg_types["confession"]), KeyboardButton(text=get_text("suggest_idea", language))]
    ]
    
    if is_admin:
        admin_commands = lang_dict["admin_commands"]
        buttons.append([KeyboardButton(text=admin_commands["admin_panel"])])
    elif is_moderator:
        mod_commands = lang_dict.get("moderator_commands", {})
        if mod_commands:
            buttons.append([KeyboardButton(text=mod_commands["moderator_panel"])])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_panel_keyboard(language='en'):
    """Get admin panel keyboard (English-only)."""
    admin_commands = TEXTS.get(language, TEXTS["en"])['admin_commands']
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=admin_commands["check_queue"])],
            [KeyboardButton(text=admin_commands["ideas_history"])],
            [KeyboardButton(text=admin_commands["add_moderator"])],
            [KeyboardButton(text=admin_commands["remove_moderator"])],
            [KeyboardButton(text=admin_commands["rename_moderator"])],
            [KeyboardButton(text=admin_commands["list_moderators"])],
            [KeyboardButton(text=admin_commands["back_main"])],
        ],
        resize_keyboard=True
    )

def get_moderator_panel_keyboard(language='en'):
    """Get moderator panel keyboard (English-only)."""
    mod_commands = TEXTS.get(language, TEXTS["en"]).get("moderator_commands", {})
    if not mod_commands:
        mod_commands = TEXTS["en"]["moderator_commands"]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=mod_commands["check_queue"])],
            [KeyboardButton(text=mod_commands["back_main"])],
        ],
        resize_keyboard=True
    )

def get_university_keyboard(language='en'):
    """Get university selection keyboard"""
    back_text = get_text("back", language)
    
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=uni)] for uni in UNIVERSITIES] + 
                [[KeyboardButton(text=back_text)]],
        resize_keyboard=True
    )

def get_back_keyboard(language='en'):
    """Get back button keyboard"""
    back_text = get_text("back", language)
    
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=back_text)]],
        resize_keyboard=True
    )

def get_after_message_keyboard(user_id, language='en', is_admin=False, is_moderator=False):
    """Get keyboard shown after message submission - returns to main menu"""
    return get_user_keyboard(user_id, language, is_admin=is_admin, is_moderator=is_moderator)

# Language handlers (disabled; English is the only language)
async def handle_language_selection(message, bot, user_data):
    """Deprecated: language selection is disabled (English-only)."""
    user_id = message.from_user.id
    update_user_language(user_id, 'en')
    await message.answer(get_text("language_changed", "en"), reply_markup=get_user_keyboard(user_id, 'en', is_admin=is_admin(user_id), is_moderator=False))
    return 'en'

# Module initialization
async def register_language_handlers(dp, bot):
    """No language commands to register (English-only)."""
    return

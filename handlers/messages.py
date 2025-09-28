"""
Message handlers module for ShadowX Bot
Handles text messages and commands
"""

from aiogram import types, F
import logging
from aiogram.filters import Command
from database import get_user, add_user, add_message_to_db, is_banned
from handlers.language import get_text, get_user_keyboard, get_back_keyboard, get_after_message_keyboard
from utils.filters import contains_banned_words, contains_banned_words_async, contains_ad_words, filter_profanity, contains_spam, spam_score
from config import ADMIN_ID, ADMIN_IDS, is_admin, UNIVERSITIES
from utils.queue import MessageQueue
import state

async def register_message_handlers(dp, bot):
    """Register message-related handlers"""
    
    # Initialize message queue
    queue_manager = MessageQueue(bot)
    await queue_manager.start()
    state.queue_manager = queue_manager
    
    @dp.message(Command("start"))
    async def start_command(message: types.Message):
        user_id = message.from_user.id
        user = get_user(user_id)
        user_data = state.user_data
        
        # Determine language and ensure default university
        language = user[3] if user and user[3] else 'en'
        default_university = 'XIAMEN'
        if (not user) or (not user[2]) or (user[2] not in UNIVERSITIES):
            add_user(user_id, message.from_user.username, default_university, language)
        
        try:
            from database import is_moderator as _is_moderator
            is_mod = _is_moderator(user_id)
        except Exception:
            logging.debug("Failed to check moderator status on /start", exc_info=True)
            is_mod = False
        await message.answer(
            get_text("select_message_type", language),
            reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
        )

    @dp.message(Command("help"))
    async def help_command(message: types.Message):
        user_id = message.from_user.id
        user = get_user(user_id)
        language = user[3] if user and user[3] else 'en'

        commands_text = "Available commands:\n/start — restart\n/help — help & rules"

        text = (
            f"{get_text('welcome', language)}\n\n"
            f"{get_text('intro', language)}"
            f"{get_text('rules', language)}\n"
            f"{commands_text}"
        )

        # Always show main keyboard (university defaults to XIAMEN)
        try:
            from database import is_moderator as _is_moderator
            is_mod = _is_moderator(user_id)
        except Exception:
            logging.debug("Failed to check moderator status on /help", exc_info=True)
            is_mod = False
        await message.answer(
            text,
            reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
        )
    
    # Disclaimer confirmation flow removed; users go straight to main menu
    
    # University selection flow removed; default university is set automatically
    
    @dp.message(lambda message: message.text in [
        get_text("message_types.help", "en"),
        get_text("message_types.regular", "en"),
        get_text("message_types.confession", "en"),
    ])
    async def handle_message_type_selection(message: types.Message):
        user_id = message.from_user.id
        user = get_user(user_id)
        user_data = state.user_data
        
        # Ensure default university exists
        if (not user) or (not user[2]) or (user[2] not in UNIVERSITIES):
            language = user[3] if user and user[3] else 'en'
            add_user(user_id, message.from_user.username, 'XIAMEN', language)
            user = get_user(user_id)

        language = user[3] if user[3] else 'en'
        
        if user_id not in user_data:
            user_data[user_id] = {}
        
        user_data[user_id]['message_type'] = message.text
        # If user selected Confession, show a focused prompt
        selected = message.text
        prompt = get_text("write_message", language)
        if selected == get_text("message_types.confession", language):
            prompt = "💞 Send your confession anonymously. Avoid personal data or doxxing."
        await message.answer(prompt, reply_markup=get_back_keyboard(language))

    @dp.message(Command("confession"))
    async def confession_command(message: types.Message):
        """Shortcut command to start a confession submission."""
        user_id = message.from_user.id
        user = get_user(user_id)
        language = user[3] if user and user[3] else 'en'
        if user_id not in state.user_data:
            state.user_data[user_id] = {}
        state.user_data[user_id]['message_type'] = get_text("message_types.confession", language)
        await message.answer(
            "💞 Send your confession anonymously. Avoid personal data or doxxing.",
            reply_markup=get_back_keyboard(language)
        )
    
    # Suggest Idea entry point
    @dp.message(lambda message: message.text in [get_text("suggest_idea", "en")])
    async def handle_suggest_idea_button(message: types.Message):
        user_id = message.from_user.id
        user = get_user(user_id)
        language = user[3] if user and user[3] else 'en'
        if user_id not in state.user_data:
            state.user_data[user_id] = {}
        state.user_data[user_id]['awaiting_idea'] = True
        await message.answer(get_text("write_idea", language), reply_markup=get_back_keyboard(language))

    @dp.message(lambda message: message.text in [get_text("back", "en")])
    async def handle_back_command(message: types.Message):
        user_id = message.from_user.id
        user_data = state.user_data
        
        # Get user's language
        user = get_user(user_id)
        language = user[3] if user and user[3] else 'en'
        
        if user_id in user_data:
            user_data[user_id].pop('message_type', None)
            user_data[user_id].pop('awaiting_idea', None)
            try:
                from database import is_moderator as _is_moderator
                is_mod = _is_moderator(user_id)
            except Exception:
                logging.debug("Failed to check moderator status on back", exc_info=True)
                is_mod = False
            await message.answer(
                get_text("main_menu", language),
                reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
        else:
            await start_command(message)
    
    # University change request flow removed
    
    @dp.message(F.text)
    async def handle_text_message(message: types.Message):
        user_id = message.from_user.id
        if is_banned(user_id):
            return
        user = get_user(user_id)
        user_data = state.user_data
        
        # Skip processing for commands processed by other handlers
        if message.text.startswith('/'):
            return
        
        # Language selection UI is removed; no need to handle flag buttons
        
        # Skip admin command buttons
        admin_commands = [
            get_text("admin_commands.check_queue", "en")
        ]
        if message.text in admin_commands:
            return

        # Handle idea text if awaiting
        if user_id in user_data and user_data[user_id].get('awaiting_idea'):
            language = user[3] if user and user[3] else 'en'
            try:
                from database import add_idea
                idea_id = add_idea(user_id=user_id, content=message.text)
            except Exception:
                logging.debug("Failed to store idea", exc_info=True)
                idea_id = None
            # Notify all admins
            for admin_id in ADMIN_IDS:
                try:
                    # Prefer live username from the message; fallback to stored DB username; else ID
                    display_name = None
                    if getattr(message.from_user, 'username', None):
                        display_name = f"@{message.from_user.username}"
                    else:
                        try:
                            u2 = get_user(user_id)
                            if u2 and u2[1]:
                                display_name = f"@{u2[1]}"
                        except Exception:
                            display_name = None
                    if not display_name:
                        display_name = f"ID:{user_id}"
                    await bot.send_message(
                        admin_id,
                        f"💡 New idea (ID: {idea_id}) from {display_name}:\n\n{message.text}"
                    )
                except Exception:
                    logging.warning("Failed to notify admin about idea", exc_info=True)
            # Clear state and return to menu
            user_data[user_id]['awaiting_idea'] = False
            try:
                from database import is_moderator as _is_moderator
                is_mod = _is_moderator(user_id)
            except Exception:
                is_mod = False
            await message.answer(
                get_text("idea_received", language),
                reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
            return
        
        # Ensure user exists with default university
        if not user or not user[2] or user[2] not in UNIVERSITIES:
            language = user[3] if user and user[3] else 'en'
            add_user(user_id, message.from_user.username, 'XIAMEN', language)
            user = get_user(user_id)
        
        if user_id not in user_data or 'message_type' not in user_data[user_id]:
            language = user[3] if user[3] else 'en'
            await message.answer(
                get_text("message_type_first", language),
                reply_markup=get_user_keyboard(user_id, language)
            )
            return
        
        text = message.text
        university = user[2]
        message_type = user_data[user_id]['message_type']
        language = user[3] if user and user[3] else 'en'
        # Removed minimal words enforcement
        
        # Check for ads/profanity/spam; these go to admin
        has_ads = contains_ad_words(text)
        has_profanity = await contains_banned_words_async(text)
        has_spam = contains_spam(text)

        if has_ads or has_profanity or has_spam:
            # For ads or profanity, send to moderation; mask profanity if present
            filtered_text = filter_profanity(text) if has_profanity else text

            # Determine reasons for DB and admin
            if has_ads and has_profanity and has_spam:
                reason_db = 'Ads + Profanity + Spam'
                reason_admin = 'Ad+Profanity+Spam'
            elif has_ads and has_profanity:
                reason_db = 'Ads + Profanity'
                reason_admin = 'Ad+Profanity'
            elif has_ads and has_spam:
                reason_db = f'Ads + Spam (score={spam_score(text):.2f})'
                reason_admin = f'Ad+Spam ({spam_score(text):.2f})'
            elif has_profanity and has_spam:
                reason_db = f'Profanity + Spam (score={spam_score(text):.2f})'
                reason_admin = f'Profanity+Spam ({spam_score(text):.2f})'
            elif has_ads:
                reason_db = 'Possible advertisement detected'
                reason_admin = 'Possible ad'
            elif has_spam:
                s = spam_score(text)
                reason_db = f'Possible spam (score={s:.2f})'
                reason_admin = f'Possible spam ({s:.2f})'
            else:
                reason_db = 'Banned words detected'
                reason_admin = 'Profanity detected'

            message_id = add_message_to_db(
                user_id=user_id,
                university=university,
                message_type=message_type,
                content=text,
                filtered_content=filtered_text,
                status='pending',
                reason=reason_db
            )

            if message_id:
                state.moderation_queue[message_id] = {
                    'user_id': user_id,
                    'text': text,
                    'filtered_text': filtered_text,
                    'university': university,
                    'message_type': message_type,
                    'reason': reason_admin,
                    'language': language
                }

                from handlers.moderation import get_admin_decision_keyboard
                from database import get_moderators
                recipients = set(get_moderators() or [])
                recipients.update(ADMIN_IDS)
                for recipient_id in recipients:
                    try:
                        # Localize buttons for each recipient
                        try:
                            admin_user = get_user(recipient_id)
                            admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                        except Exception:
                            admin_language = 'en'
                        await bot.send_message(
                            recipient_id,
                            f"⚠️ Message for moderation (ID: {message_id})\n\n"
                            f"🏫 University: {university}\n"
                            f"📌 Type: {message_type}\n"
                            f"🔎 Reason: {reason_admin}\n\n"
                            f"📝 Original text:\n{text}\n\n"
                            f"🧹 Filtered text:\n{filtered_text}",
                            reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                        )
                    except Exception:
                        pass

                # Notify user and return to main menu
                try:
                    from database import is_moderator as _is_moderator
                    is_mod = _is_moderator(user_id)
                except Exception:
                    is_mod = False
                await message.answer(
                    get_text("message_moderation", language),
                    reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
                )
                # Clear selection
                try:
                    user_data[user_id].pop('message_type', None)
                except Exception:
                    logging.debug("Failed to clear message_type after moderation enqueue", exc_info=True)
            else:
                await message.answer(
                    get_text("error", language),
                    reply_markup=get_user_keyboard(user_id, language)
                )
        else:
            # No ads and not sensitive type: auto-approve. If profanity only, mask and publish.
            filtered_text = filter_profanity(text) if has_profanity else None

            message_id = add_message_to_db(
                user_id=user_id,
                university=university,
                message_type=message_type,
                content=text,
                filtered_content=filtered_text,
                status='approved'
            )

            if message_id:
                state.queue_manager.schedule_message(message_id)

                try:
                    from database import is_moderator as _is_moderator
                    is_mod = _is_moderator(user_id)
                except Exception:
                    is_mod = False
                await message.answer(
                    get_text("message_queued", language),
                    reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
                )
                # Clear selection
                try:
                    user_data[user_id].pop('message_type', None)
                except Exception:
                    logging.debug("Failed to clear message_type after queueing", exc_info=True)
            else:
                await message.answer(
                    get_text("error", language),
                    reply_markup=get_user_keyboard(user_id, language)
                )
    
    # Ensure state module is initialized
    state.user_data = state.user_data

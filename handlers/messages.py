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
import re

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

    @dp.message(Command("anon"))
    async def cmd_send_anon_message(message: types.Message):
        """Allow any user to send an anonymous reply to the author of a published post by its number.
        Usage:
            /anon <number> <text>
        If text is omitted, bot will prompt for it in next message.
        """
        user_id = message.from_user.id
        user = get_user(user_id)
        language = user[3] if user and user[3] else 'en'

        text = message.text or ''
        # Parse: command + number + optional text
        m = re.match(r"^/anon\s+(\d+)(?:\s+(.+))?$", text.strip(), flags=re.IGNORECASE | re.DOTALL)
        if not m:
            await message.answer(
                "How to use:\n"
                "1) Find the post number in the channel (e.g., №42).\n"
                "2) Send: /anon 42 Your message here\n\n"
                "Example:\n/anon 42 Hello! Let's connect."
            )
            return
        post_number = int(m.group(1))
        reply_text = (m.group(2) or '').strip()

        # Resolve author by number (optionally could use user's university context)
        try:
            from database import get_author_by_published_number
            author_user_id, source_message_id = get_author_by_published_number(post_number)
        except Exception:
            author_user_id, source_message_id = (None, None)
        if not author_user_id:
            await message.answer("Post not found or mapping not available yet.")
            return

        if not reply_text:
            # Ask for message in next step
            state.user_data[user_id] = state.user_data.get(user_id, {})
            st = state.user_data[user_id]
            st['awaiting_anon_reply'] = True
            st['anon_reply_target'] = {
                'author_id': author_user_id,
                'post_number': post_number,
                'source_message_id': source_message_id
            }
            await message.answer(
                "Please send your anonymous reply text now.\n"
                "Tip: Be respectful and avoid sharing personal data."
            )
            return

        # Send immediately
        try:
            await message.bot.send_message(author_user_id, f"📩 Anonymous reply to your post №{post_number}:\n\n{reply_text}")
            await message.answer("✅ Sent to the author.")
        except Exception:
            await message.answer("Failed to deliver message to the author.")
    
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
            try:
                await message.answer(
                    get_text("main_menu", language),
                    reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
                )
            except Exception:
                # Network hiccup; try once more shortly
                try:
                    import asyncio as _asyncio
                    await _asyncio.sleep(1)
                    await message.answer(
                        get_text("main_menu", language),
                        reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
                    )
                except Exception:
                    # Give up silently to avoid user-visible tracebacks
                    pass
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
        
        # Skip admin command buttons, but if it's Check queue and moderation handler didn't catch it,
        # provide a graceful empty-queue response here for admins/moderators.
        admin_commands = [
            get_text("admin_commands.check_queue", "en")
        ]
        if message.text in admin_commands:
            try:
                from database import is_moderator as _is_moderator, get_user as _get_user
                # Only allow admins/moderators
                if not (is_admin(message.from_user.id) or _is_moderator(message.from_user.id)):
                    return
                # If moderation handler wasn't triggered and queue is empty, answer here
                try:
                    from database import get_pending_messages as _get_pending
                    pending = _get_pending() or []
                except Exception:
                    pending = []
                if not pending:
                    try:
                        u = _get_user(message.from_user.id)
                        lang = u[3] if u and u[3] else 'en'
                    except Exception:
                        lang = 'en'
                    await message.answer(get_text('result.queue_empty', lang))
                # Otherwise do nothing and let the user press again or rely on moderation handler
            except Exception:
                pass
            return

        # Handle idea text if awaiting
        # Handle awaiting anonymous reply composition flow
        if user_id in user_data and user_data[user_id].get('awaiting_anon_reply'):
            payload = user_data[user_id].get('anon_reply_target') or {}
            target_id = payload.get('author_id')
            post_number = payload.get('post_number')
            if not target_id:
                # Reset state gracefully
                user_data[user_id]['awaiting_anon_reply'] = False
                user_data[user_id].pop('anon_reply_target', None)
                await message.answer("Session expired. Use /anon <number> again.")
                return
            reply_text = message.text.strip()
            try:
                await message.bot.send_message(target_id, f"📩 Anonymous reply to your post №{post_number}:\n\n{reply_text}")
                await message.answer("✅ Sent to the author.")
            except Exception:
                await message.answer("Failed to deliver message to the author.")
            # Clear anon reply state and fall through to main menu
            user_data[user_id]['awaiting_anon_reply'] = False
            user_data[user_id].pop('anon_reply_target', None)
            try:
                from database import is_moderator as _is_moderator
                is_mod = _is_moderator(user_id)
            except Exception:
                is_mod = False
            await message.answer(
                get_text("main_menu", language),
                reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
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

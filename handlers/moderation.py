"""
Moderation handlers module for ShadowX Bot
Handles message/media approval and rejection
"""

from aiogram import types, F
import logging
from aiogram.filters import Command
from database import update_message_status, get_message
from database import get_pending_messages, clear_pending_queue, clear_pending_messages
from handlers.language import (
    get_text,
    get_user_keyboard,
    get_after_message_keyboard,
    get_admin_panel_keyboard,
    get_moderator_panel_keyboard,
)
from config import ADMIN_ID, ADMIN_IDS, is_admin, UNIVERSITIES
import state
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database import get_user, get_moderator_name
from database import get_ideas_count, get_ideas_page, get_idea_by_id

# Notification functions
async def notify_admins_about_moderator_action(bot, moderator_id, action_type, user_id, content, caption=None, message_id=None):
    """Notify all admins about moderator actions"""
    try:
        # Get moderator name from database (saved when moderator was added)
        moderator_name = get_moderator_name(moderator_id)
        if not moderator_name:
            moderator_name = f"ID:{moderator_id}"
        
        # Prepare content for notification (show full content, not truncated)
        display_content = content if content else (caption if caption else "Нет содержимого")
        
        # Send notification to all admins
        for admin_id in ADMIN_IDS:
            try:
                # Get admin language
                admin_user = get_user(admin_id)
                admin_language = admin_user[3] if admin_user and admin_user[3] else 'ru'
                
                # Get localized notification text
                try:
                    notification_text = get_text(f"moderator_actions.{action_type}", admin_language).format(
                        moderator=moderator_name,
                        user_id=user_id,
                        content=display_content,
                        caption=display_content if caption else "",
                        message_id=message_id if message_id else "N/A"
                    )
                except KeyError as e:
                    logging.warning(f"Missing translation key: moderator_actions.{action_type} for language {admin_language}")
                    # Fallback notification
                    action_emoji = "✅" if "approved" in action_type else "❌"
                    content_type_ru = "медиа" if "media" in action_type else "сообщение"
                    action_ru = "одобрил" if "approved" in action_type else "отклонил"
                    notification_text = f"{action_emoji} Модератор {moderator_name} {action_ru} {content_type_ru} #{message_id} от пользователя {user_id}:\n\n📝 {display_content}"
                
                await bot.send_message(admin_id, notification_text)
                
            except Exception as e:
                logging.warning(f"Failed to notify admin {admin_id}: {e}")
                
    except Exception as e:
        logging.exception(f"Error in notify_admins_about_moderator_action: {e}")

# Admin decision keyboards
def get_admin_decision_keyboard(message_id, language='ru'):
    """Get admin decision keyboard for message moderation (localized, no skip)."""
    if language == 'en':
        approve_text = "✅ Approve"
        reject_text = "❌ Reject"
    else:
        approve_text = "✅ Одобрить"
        reject_text = "❌ Отклонить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=approve_text, callback_data=f"approve_{message_id}"),
            InlineKeyboardButton(text=reject_text, callback_data=f"reject_{message_id}")
        ]
    ])

def get_university_change_decision_keyboard(request_id):
    """Deprecated: University change flow removed"""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Disabled", callback_data=f"unichange_reject_{request_id}")]])

async def register_moderation_handlers(dp, bot):
    """Register moderation-related handlers"""
    
    @dp.message(lambda message: message.text in [
        get_text("admin_commands.check_queue", "ru"),
        get_text("admin_commands.check_queue", "en"),
        # Allow via moderator panel as well (same label)
        get_text("moderator_commands.check_queue", "ru"),
        get_text("moderator_commands.check_queue", "en"),
    ])
    async def show_moderation_queue_handler(message: types.Message):
        # Admins and moderators can view the queue
        try:
            from database import is_moderator as _is_moderator
            allowed = is_admin(message.from_user.id) or _is_moderator(message.from_user.id)
        except Exception:
            allowed = is_admin(message.from_user.id)
        if not allowed:
            return
        
        pending_messages = get_pending_messages()
        if not pending_messages:
            # Localize empty state by user's language
            try:
                from database import get_user as _get_user
                u = _get_user(message.from_user.id)
                lang = u[3] if u and u[3] else 'ru'
            except Exception:
                lang = 'ru'
            await message.answer(get_text('result.queue_empty', lang))
            return
        
        # Determine admin language for localized buttons
        try:
            from database import get_user as _get_user
            admin_user = _get_user(message.from_user.id)
            admin_language = admin_user[3] if admin_user and admin_user[3] else 'ru'
        except Exception:
            admin_language = 'ru'

        for msg in pending_messages:
            message_id, user_id, university, message_type, content, filtered_content, media_type, file_id, status, reason, timestamp = msg
            
            if media_type:  # Media message
                if media_type == "photo":
                    await bot.send_photo(
                        message.chat.id,
                        photo=file_id,
                        caption=f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}",
                        reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                    )
                elif media_type == "video":
                    await bot.send_video(
                        message.chat.id,
                        video=file_id,
                        caption=f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}",
                        reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                    )
                elif media_type == "audio":
                    await bot.send_audio(
                        message.chat.id,
                        audio=file_id,
                        caption=f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}",
                        reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                    )
                elif media_type == "voice":
                    await bot.send_voice(
                        message.chat.id,
                        voice=file_id,
                        caption=f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}",
                        reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                    )
                elif media_type == "video_note":
                    # Video notes don't support captions; send separate message with buttons
                    await bot.send_video_note(
                        message.chat.id,
                        video_note=file_id
                    )
                    await bot.send_message(
                        message.chat.id,
                        f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}",
                        reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                    )
            else:  # Text message
                original = content
                filtered = filtered_content if filtered_content else content
                
                # Show both versions if different
                if filtered != original:
                    text = f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}\n\n"
                    text += f"Original:\n{original}\n\nFiltered:\n{filtered}"
                else:
                    text = f"ID: {message_id}\nUniversity: {university}\nType: {message_type}\nStatus: {status}\n\nText: {content}"
                
                await message.answer(
                    text,
                    reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                )
    
    # University change requests UI removed
    
    @dp.callback_query(lambda c: c.data.startswith(('approve_', 'reject_')))
    async def process_moderation_decision(callback_query: types.CallbackQuery):
        """Process admin decision for message moderation"""
        action, message_id = callback_query.data.split('_')
        message_id = int(message_id)
        # Answer early to avoid "query is too old" errors if processing takes time
        try:
            await callback_query.answer()
        except Exception:
            pass
        
        # Get moderation queue from shared state
        moderation_queue = state.moderation_queue
        
        if message_id not in moderation_queue:
            # Fallback: attempt to reconstruct message data from the database (after restart)
            try:
                db_msg = get_message(message_id)
            except Exception:
                db_msg = None
            if not db_msg:
                await callback_query.answer("Message not found")
                return
            # Ensure message still pending
            try:
                current_status = db_msg[8]  # status
            except Exception:
                current_status = None
            if current_status != 'pending':
                await callback_query.answer("Message already processed")
                return
            # Unpack DB row (see database.py messages schema)
            try:
                db_user_id = db_msg[1]
                db_university = db_msg[2]
                db_message_type = db_msg[3]
                db_content = db_msg[4]
                db_filtered = db_msg[5]
                db_media_type = db_msg[6]
                db_file_id = db_msg[7]
            except Exception:
                await callback_query.answer("Internal error")
                return
            # Determine user language for notifications
            try:
                u = get_user(db_user_id)
                language = u[3] if u and u[3] else 'ru'
            except Exception:
                language = 'ru'
            # Reconstruct moderation payload compatible with rest of flow
            if db_media_type:
                rebuilt = {
                    'user_id': db_user_id,
                    'media_type': db_media_type,
                    'file_id': db_file_id,
                    'caption': db_content or "",
                    'university': db_university,
                    'message_type': db_message_type,
                    'language': language,
                }
            else:
                rebuilt = {
                    'user_id': db_user_id,
                    'text': db_content or "",
                    'filtered_text': db_filtered or None,
                    'university': db_university,
                    'message_type': db_message_type,
                    'language': language,
                }
            moderation_queue[message_id] = rebuilt
        
        message_data = moderation_queue[message_id]
        user_id = message_data['user_id']
        university = message_data['university']
        message_type = message_data['message_type']
        language = message_data.get('language', 'ru')
        
        # Update message status in database
        if action == 'approve':
            new_status = 'approved'
            status_text = 'approved'
        elif action == 'reject':
            new_status = 'rejected'
            status_text = 'rejected'
        else:
            # Unknown action fallback
            await callback_query.answer("Unsupported action")
            return
        
        update_message_status(message_id, new_status)
        
        if action == 'approve':
            # Add to sending queue
            state.queue_manager.schedule_message(message_id)
            
            # Notify user that message is queued (final published notice will be sent after posting)
            content_type = 'media' if 'media_type' in message_data else 'message'
            if content_type == 'media':
                notification = get_text('media_queued', language)
            else:
                notification = get_text('message_queued', language)
            
            try:
                from database import is_moderator as _is_moderator
                is_mod = _is_moderator(user_id)
            except Exception:
                is_mod = False
            await bot.send_message(
                user_id,
                notification,
                reply_markup=get_after_message_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
        elif action == 'reject':
            # Notify user about rejection
            content_type = 'media' if 'media_type' in message_data else 'message'
            if content_type == 'media':
                notification = get_text('media_rejected', language)
            else:
                notification = get_text('message_rejected', language)
            
            try:
                from database import is_moderator as _is_moderator
                is_mod = _is_moderator(user_id)
            except Exception:
                is_mod = False
            await bot.send_message(
                user_id,
                notification,
                reply_markup=get_after_message_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
        
        # Notify admins about moderator action (only if moderator is not admin)
        moderator_id = callback_query.from_user.id
        
        if not is_admin(moderator_id):
            content_type = 'media' if 'media_type' in message_data else 'message'
            # Properly form action type key
            if action == 'approve':
                action_suffix = 'approved'
            elif action == 'reject':
                action_suffix = 'rejected'
            else:
                action_suffix = f"{action}d"
            
            action_type = f"{content_type}_{action_suffix}"  # message_approved, media_rejected, etc.
            
            # Get the actual content based on message type
            if content_type == 'media':
                content = message_data.get('caption', '')
                caption = content
            else:
                # For text messages, show original text or filtered text
                content = message_data.get('text', '') or message_data.get('filtered_text', '')
                caption = None
            
            await notify_admins_about_moderator_action(
                bot, moderator_id, action_type, user_id, content, caption, message_id
            )
        
        # Update admin UI (edit text for text messages, caption for media)
        admin_status = (
            f"Message {message_id} {status_text}\n"
            f"University: {university}\n"
            f"Type: {message_type}"
        )
        try:
            if getattr(callback_query.message, 'photo', None) or getattr(callback_query.message, 'video', None):
                await callback_query.message.edit_caption(admin_status)
            else:
                await callback_query.message.edit_text(admin_status)
        except Exception:
            # Fallback: ignore UI update errors
            pass
        
        # Remove from moderation queue
        moderation_queue.pop(message_id, None)
        
        # Already answered early; ignore errors if trying again
        try:
            await callback_query.answer()
        except Exception:
            pass
    
    # Panels
    @dp.message(lambda message: message.text in [
        get_text("admin_commands.admin_panel", "ru"),
        get_text("admin_commands.admin_panel", "en"),
    ])
    async def open_admin_panel(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            from database import get_user as _get_user
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        await message.answer(get_text('menu.admin_title', lang), reply_markup=get_admin_panel_keyboard(lang))

    # ---- Ideas history (admin only) ----
    def _ideas_nav_keyboard(language: str, page: int, pages: int, base_cb: str = "ideas"):
        prev_btn = InlineKeyboardButton(text=get_text("ideas.prev", language), callback_data=f"{base_cb}_prev_{page}")
        next_btn = InlineKeyboardButton(text=get_text("ideas.next", language), callback_data=f"{base_cb}_next_{page}")
        return InlineKeyboardMarkup(inline_keyboard=[[prev_btn, next_btn]])

    def _ideas_open_keyboard(language: str, idea_id: int):
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_text("ideas.open", language), callback_data=f"idea_open_{idea_id}")]])

    async def _send_ideas_page(chat_id: int, language: str, page: int = 1, page_size: int = 5, edit_message: types.Message | None = None):
        total = max(0, get_ideas_count())
        pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, pages))
        offset = (page - 1) * page_size
        ideas = get_ideas_page(offset, page_size)
        header = get_text("ideas.title", language)
        page_info = get_text("ideas.page", language).format(page=page, pages=pages, total=total)
        if not ideas:
            text = f"{header}\n\n{get_text('ideas.empty', language)}\n{page_info}"
            if edit_message:
                try:
                    await edit_message.edit_text(text)
                except Exception:
                    await bot.send_message(chat_id, text)
            else:
                await bot.send_message(chat_id, text)
            return
        # Build a nicely formatted list
        lines = [header, ""]
        for idea_id, user_id, content, media_type, file_id, ts in ideas:
            # Prefer stored DB username if available
            try:
                uinfo = get_user(user_id)
                uname = (uinfo[1] if uinfo and uinfo[1] else None)
            except Exception:
                uname = None
            user_label = f"@{uname}" if uname else f"ID:{user_id}"
            icon = "🖼" if media_type in ("photo", "video", "audio", "voice", "video_note", "poll") else "📝"
            preview = (content or "").strip()
            if preview and len(preview) > 120:
                preview = preview[:117] + "…"
            item_line = f"{icon} #{idea_id} • {ts} • {user_label}\n{preview or '-'}"
            lines.append(item_line)
            lines.append("")
        text = "\n".join(lines) + f"\n{page_info}"
        kb = _ideas_nav_keyboard(language, page, pages, base_cb="ideas")
        if edit_message:
            try:
                await edit_message.edit_text(text, reply_markup=kb)
            except Exception:
                await bot.send_message(chat_id, text, reply_markup=kb)
        else:
            await bot.send_message(chat_id, text, reply_markup=kb)

    @dp.message(lambda message: message.text in [
        get_text("admin_commands.ideas_history", "ru"),
        get_text("admin_commands.ideas_history", "en"),
    ])
    async def cmd_ideas_history(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            from database import get_user as _get_user
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        await _send_ideas_page(message.chat.id, lang, page=1)

    @dp.callback_query(lambda c: c.data.startswith(('ideas_prev_', 'ideas_next_')))
    async def ideas_pagination(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id
        if not is_admin(user_id):
            return
        # Determine language
        try:
            u = get_user(user_id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        # Parse action
        try:
            action, _, page_str = callback_query.data.partition('_prev_' if '_prev_' in callback_query.data else '_next_')
            current_page = int(page_str)
        except Exception:
            current_page = 1
        await callback_query.answer()
        total = max(0, get_ideas_count())
        pages = max(1, (total + 5 - 1) // 5)
        if 'prev' in callback_query.data:
            target = max(1, current_page - 1)
        else:
            target = min(pages, current_page + 1)
        await _send_ideas_page(callback_query.message.chat.id, lang, page=target, edit_message=callback_query.message)

    @dp.callback_query(lambda c: c.data.startswith('idea_open_'))
    async def idea_open(callback_query: types.CallbackQuery):
        user_id = callback_query.from_user.id
        if not is_admin(user_id):
            return
        try:
            idea_id = int(callback_query.data.split('_')[-1])
        except Exception:
            await callback_query.answer()
            return
        await callback_query.answer()
        idea = get_idea_by_id(idea_id)
        # Determine language
        try:
            u = get_user(user_id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        if not idea:
            await bot.send_message(callback_query.message.chat.id, get_text('ideas.empty', lang))
            return
        _, uid, content, media_type, file_id, ts = idea
        try:
            uinfo = get_user(uid)
            uname = (uinfo[1] if uinfo and uinfo[1] else None)
        except Exception:
            uname = None
        user_label = f"@{uname}" if uname else f"ID:{uid}"
        header = f"#{idea_id} • {ts} • {user_label}"
        if media_type in ("photo", "video", "audio", "voice", "video_note"):
            caption = (content or '').strip() or header
            try:
                if media_type == 'photo':
                    await bot.send_photo(callback_query.message.chat.id, photo=file_id, caption=caption)
                elif media_type == 'video':
                    await bot.send_video(callback_query.message.chat.id, video=file_id, caption=caption)
                elif media_type == 'audio':
                    await bot.send_audio(callback_query.message.chat.id, audio=file_id, caption=caption)
                elif media_type == 'voice':
                    await bot.send_voice(callback_query.message.chat.id, voice=file_id, caption=caption)
                elif media_type == 'video_note':
                    await bot.send_video_note(callback_query.message.chat.id, video_note=file_id)
                    if content:
                        await bot.send_message(callback_query.message.chat.id, header + "\n" + content)
                return
            except Exception:
                pass
        # Fallback to text view
        body = (content or '').strip()
        text = f"{header}\n\n{body or '-'}"
        await bot.send_message(callback_query.message.chat.id, text)

    @dp.message(lambda message: message.text in [
        get_text("moderator_commands.moderator_panel", "ru"),
        get_text("moderator_commands.moderator_panel", "en"),
    ])
    async def open_moderator_panel(message: types.Message):
        try:
            from database import is_moderator as _is_moderator, get_user as _get_user
            if not _is_moderator(message.from_user.id) and not is_admin(message.from_user.id):
                return
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        await message.answer(get_text('menu.moderator_title', lang), reply_markup=get_moderator_panel_keyboard(lang))

    @dp.message(lambda message: message.text in [
        get_text("admin_commands.back_main", "ru"),
        get_text("admin_commands.back_main", "en"),
        get_text("moderator_commands.back_main", "ru"),
        get_text("moderator_commands.back_main", "en"),
    ])
    async def back_to_main_menu(message: types.Message):
        try:
            from database import get_user as _get_user, is_moderator as _is_moderator
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
            is_mod = _is_moderator(message.from_user.id)
        except Exception:
            lang = 'ru'
            is_mod = False
        await message.answer(
            get_text("main_menu", lang),
            reply_markup=get_user_keyboard(message.from_user.id, lang, is_admin=is_admin(message.from_user.id), is_moderator=is_mod)
        )

    # Moderators management (admin only)
    @dp.message(lambda message: message.text in [
        get_text("admin_commands.add_moderator", "ru"),
        get_text("admin_commands.add_moderator", "en")
    ])
    async def cmd_add_moderator(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            from database import get_user as _get_user
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        # Show a small keyboard with Back to main / Back for cancelling input
        back_main = get_text('admin_commands.back_main', lang)
        back = get_text('back', lang)
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=back_main)],[KeyboardButton(text=back)]], resize_keyboard=True)
        await message.answer(get_text('prompts.enter_mod_id_add', lang), reply_markup=kb)
        state.user_data[message.from_user.id] = state.user_data.get(message.from_user.id, {})
        st = state.user_data[message.from_user.id]
        st['awaiting_add_mod_id'] = True

    @dp.message(lambda message: message.text in [
        get_text("admin_commands.remove_moderator", "ru"),
        get_text("admin_commands.remove_moderator", "en")
    ])
    async def cmd_remove_moderator(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            from database import get_user as _get_user
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        back_main = get_text('admin_commands.back_main', lang)
        back = get_text('back', lang)
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=back_main)],[KeyboardButton(text=back)]], resize_keyboard=True)
        await message.answer(get_text('prompts.enter_mod_id_remove', lang), reply_markup=kb)
        state.user_data[message.from_user.id] = state.user_data.get(message.from_user.id, {})
        state.user_data[message.from_user.id]['awaiting_remove_mod'] = True

    @dp.message(lambda message: message.text in [
        get_text("admin_commands.rename_moderator", "ru"),
        get_text("admin_commands.rename_moderator", "en")
    ])
    async def cmd_rename_moderator(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            from database import get_user as _get_user
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        back_main = get_text('admin_commands.back_main', lang)
        back = get_text('back', lang)
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=back_main)],[KeyboardButton(text=back)]], resize_keyboard=True)
        await message.answer(get_text('prompts.enter_mod_id_rename', lang), reply_markup=kb)
        state.user_data[message.from_user.id] = state.user_data.get(message.from_user.id, {})
        state.user_data[message.from_user.id]['awaiting_rename_mod_id'] = True

    @dp.message(lambda message: message.text in [
        get_text("admin_commands.list_moderators", "ru"),
        get_text("admin_commands.list_moderators", "en")
    ])
    async def cmd_list_moderators(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            from database import get_user as _get_user, get_moderators_with_names
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'
        mods = []
        try:
            mods = get_moderators_with_names() or []
        except Exception:
            mods = []
        if not mods:
            await message.answer(get_text('result.mod_not_found', lang))
        else:
            header = get_text("admin_commands.list_moderators", lang)
            lines = []
            for uid, name, added in mods:
                display = name or "-"
                lines.append(f"{uid} — {display}")
            await message.answer(f"{header}:\n" + "\n".join(lines))

    @dp.message(lambda message: is_admin(message.from_user.id) and (
        state.user_data.get(message.from_user.id, {}).get('awaiting_add_mod_id') or
        state.user_data.get(message.from_user.id, {}).get('awaiting_add_mod_name') or
        state.user_data.get(message.from_user.id, {}).get('awaiting_remove_mod') or
        state.user_data.get(message.from_user.id, {}).get('awaiting_rename_mod_id') or
        state.user_data.get(message.from_user.id, {}).get('awaiting_rename_mod_name')
    ))
    async def handle_admin_mod_input(message: types.Message):
        # handle numeric inputs for add/remove after prompts (admin only)
        st = state.user_data.get(message.from_user.id, {})
        # Localize
        try:
            from database import get_user as _get_user
            u = _get_user(message.from_user.id)
            lang = u[3] if u and u[3] else 'ru'
        except Exception:
            lang = 'ru'

        # Allow cancelling with Back buttons
        back_main = get_text('admin_commands.back_main', lang)
        back = get_text('back', lang)
        if message.text in (back_main, back):
            # clear all awaiting flags for this admin
            for key in (
                'awaiting_add_mod_id', 'awaiting_add_mod_name', 'pending_mod_id',
                'awaiting_remove_mod', 'awaiting_rename_mod_id', 'awaiting_rename_mod_name'
            ):
                st.pop(key, None)
            await message.answer(get_text('menu.admin_title', lang), reply_markup=get_admin_panel_keyboard(lang))
            return

        if st.get('awaiting_add_mod_id'):
            try:
                mod_id = int(message.text.strip())
            except Exception:
                await message.answer(get_text('prompts.numeric_id', lang))
                return
            st['pending_mod_id'] = mod_id
            st['awaiting_add_mod_id'] = False
            st['awaiting_add_mod_name'] = True
            await message.answer(get_text('prompts.enter_mod_name', lang))
            return
        if st.get('awaiting_add_mod_name'):
            name = message.text.strip()
            mod_id = st.get('pending_mod_id')
            from database import add_moderator
            add_moderator(mod_id, name)
            st['awaiting_add_mod_name'] = False
            st.pop('pending_mod_id', None)
            await message.answer(get_text('result.mod_added', lang).format(id=mod_id, name=name), reply_markup=get_admin_panel_keyboard(lang))
            return
        if st.get('awaiting_remove_mod'):
            try:
                mod_id = int(message.text.strip())
            except Exception:
                await message.answer(get_text('prompts.numeric_id', lang))
                return
            # prevent removing any admin
            if mod_id in ADMIN_IDS:
                await message.answer(get_text('result.cannot_remove_admin', lang))
                st['awaiting_remove_mod'] = False
                return
            from database import remove_moderator
            removed = remove_moderator(mod_id)
            st['awaiting_remove_mod'] = False
            if removed:
                await message.answer(get_text('result.mod_removed', lang).format(id=mod_id), reply_markup=get_admin_panel_keyboard(lang))
            else:
                await message.answer(get_text('result.mod_not_found', lang), reply_markup=get_admin_panel_keyboard(lang))
            return
        if st.get('awaiting_rename_mod_id'):
            try:
                mod_id = int(message.text.strip())
            except Exception:
                await message.answer(get_text('prompts.numeric_id', lang))
                return
            st['pending_mod_id'] = mod_id
            st['awaiting_rename_mod_id'] = False
            st['awaiting_rename_mod_name'] = True
            await message.answer(get_text('prompts.enter_new_name', lang))
            return
        if st.get('awaiting_rename_mod_name'):
            name = message.text.strip()
            mod_id = st.get('pending_mod_id')
            from database import set_moderator_name
            updated = set_moderator_name(mod_id, name)
            st['awaiting_rename_mod_name'] = False
            st.pop('pending_mod_id', None)
            if updated:
                await message.answer(get_text('result.mod_renamed', lang).format(id=mod_id, name=name), reply_markup=get_admin_panel_keyboard(lang))
            else:
                await message.answer(get_text('result.mod_not_found', lang), reply_markup=get_admin_panel_keyboard(lang))

    # University change callbacks removed

    @dp.message(lambda message: message.text and message.text.strip().lower().startswith('/clear_queue'))
    async def cmd_clear_queue(message: types.Message):
        """Admin-only: clear all pending items from the message queue"""
        if not is_admin(message.from_user.id):
            return
        try:
            removed_queue = clear_pending_queue()
            removed_msgs = clear_pending_messages()
            await message.answer(f"Cleared queue: {removed_queue}, rejected pending messages: {removed_msgs}")
        except Exception as e:
            await message.answer(f"Error clearing queue: {e}")
    
    

"""
Media handler module for ShadowX Bot
Handles photo and video messages
"""

from aiogram import types, F
from database import get_user, add_message_to_db, is_banned
from handlers.language import get_text, get_user_keyboard, get_after_message_keyboard, get_back_keyboard
from handlers.moderation import get_admin_decision_keyboard
from config import ADMIN_ID, ADMIN_IDS, ADMIN_USERNAME, is_admin, UNIVERSITIES, MIN_MESSAGE_WORDS
import state
from utils.filters import contains_ad_words, contains_banned_words, filter_profanity, contains_spam, spam_score

 # Use shared moderation queue from state and keyboard from moderation module

async def register_media_handlers(dp, bot):
    """Register media-related handlers"""
    
    @dp.message(F.content_type.in_({'photo', 'video', 'audio', 'voice', 'video_note'}))
    async def handle_media_message(message: types.Message):
        user_id = message.from_user.id
        if is_banned(user_id):
            return
        user_data = state.user_data
        
        user = get_user(user_id)
        
        # Ensure default university
        if (not user) or (not user[2]) or (user[2] not in UNIVERSITIES):
            language = user[3] if user and user[3] else 'en'
            try:
                from database import add_user
                add_user(user_id, message.from_user.username, 'XIAMEN', language)
            except Exception:
                pass
            user = get_user(user_id)
        
        language = user[3] if user[3] else 'en'

        # Idea media path: if awaiting_idea, send only to admin and store
        if user_id in user_data and user_data[user_id].get('awaiting_idea'):
            if message.photo:
                media_type = 'photo'
                file_id = message.photo[-1].file_id
                caption = message.caption or ""
            elif message.video:
                media_type = 'video'
                file_id = message.video.file_id
                caption = message.caption or ""
            elif getattr(message, 'video_note', None):
                media_type = 'video_note'
                file_id = message.video_note.file_id
                caption = message.caption or ""
            elif message.audio:
                media_type = 'audio'
                file_id = message.audio.file_id
                caption = message.caption or ""
            else:
                media_type = 'voice'
                file_id = message.voice.file_id
                caption = message.caption or ""
            try:
                from database import add_idea
                idea_id = add_idea(user_id=user_id, content=caption, media_type=media_type, file_id=file_id)
            except Exception:
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
                    if media_type == 'photo':
                        await bot.send_photo(
                            admin_id,
                            photo=file_id,
                            caption=f"💡 New idea (ID: {idea_id}) from {display_name}:\n\n{caption}" if caption else f"💡 New idea (ID: {idea_id}) from {display_name}"
                        )
                    elif media_type == 'video':
                        await bot.send_video(
                            admin_id,
                            video=file_id,
                            caption=f"💡 New idea (ID: {idea_id}) from {display_name}:\n\n{caption}" if caption else f"💡 New idea (ID: {idea_id}) from {display_name}"
                        )
                    elif media_type == 'video_note':
                        await bot.send_video_note(
                            admin_id,
                            video_note=file_id
                        )
                        if caption:
                            await bot.send_message(
                                admin_id,
                                f"💡 New idea (ID: {idea_id}) from {display_name}:\n\n{caption}"
                            )
                        else:
                            await bot.send_message(
                                admin_id,
                                f"💡 New idea (ID: {idea_id}) from {display_name}"
                            )
                    elif media_type == 'audio':
                        await bot.send_audio(
                            admin_id,
                            audio=file_id,
                            caption=f"💡 New idea (ID: {idea_id}) from {display_name}:\n\n{caption}" if caption else f"💡 New idea (ID: {idea_id}) from {display_name}"
                        )
                    else:
                        await bot.send_voice(
                            admin_id,
                            voice=file_id,
                            caption=f"💡 New idea (ID: {idea_id}) from {display_name}:\n\n{caption}" if caption else f"💡 New idea (ID: {idea_id}) from {display_name}"
                        )
                except Exception:
                    pass
            # Clear state, show confirmation and back to main
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
        
        if user_id not in user_data or 'message_type' not in user_data[user_id]:
            await message.answer(
                get_text("message_type_first", language),
                reply_markup=get_user_keyboard(user_id, language)
            )
            return
        
        university = user[2]
        message_type = user_data[user_id]['message_type']
        if message.photo:
            media_type = 'photo'
            file_id = message.photo[-1].file_id
            caption = message.caption or ""
        elif message.video:
            media_type = 'video'
            file_id = message.video.file_id
            caption = message.caption or ""
        elif getattr(message, 'video_note', None):
            media_type = 'video_note'
            file_id = message.video_note.file_id
            caption = message.caption or ""
        elif message.audio:
            media_type = 'audio'
            file_id = message.audio.file_id
            caption = message.caption or ""
        else:
            media_type = 'voice'
            file_id = message.voice.file_id
            # У voice нет caption в Telegram, но иногда клиенты присылают подпись
            caption = message.caption or ""
        # Enforce minimal words for caption if exists
        if caption:
            try:
                words = [w for w in caption.split() if w.strip()]
                if len(words) < MIN_MESSAGE_WORDS:
                    await message.answer(
                        get_text('prompts.min_words', language),
                        reply_markup=get_back_keyboard(language)
                    )
                    return
            except Exception:
                pass
        # Analyze caption for ads/profanity/spam
        has_ads = contains_ad_words(caption) if caption else False
        has_profanity = contains_banned_words(caption) if caption else False
        has_spam = contains_spam(caption) if caption else False
        filtered_caption = filter_profanity(caption) if has_profanity else caption

        # Determine reason for moderation UI/DB
        if has_ads and has_profanity and has_spam:
            reason_db = 'Ads + Profanity + Spam'
            reason_admin = 'Ad+Profanity+Spam'
        elif has_ads and has_profanity:
            reason_db = 'Ads + Profanity'
            reason_admin = 'Ad+Profanity'
        elif has_ads and has_spam:
            s = spam_score(caption)
            reason_db = f'Ads + Spam (score={s:.2f})'
            reason_admin = f'Ad+Spam ({s:.2f})'
        elif has_profanity and has_spam:
            s = spam_score(caption)
            reason_db = f'Profanity + Spam (score={s:.2f})'
            reason_admin = f'Profanity+Spam ({s:.2f})'
        elif has_ads:
            reason_db = 'Media requires review (possible ad)'
            reason_admin = 'Possible ad'
        elif has_spam:
            s = spam_score(caption)
            reason_db = f'Media requires review (spam score={s:.2f})'
            reason_admin = f'Possible spam ({s:.2f})'
        elif has_profanity:
            reason_db = 'Media requires review (profanity)'
            reason_admin = 'Profanity detected'
        else:
            reason_db = 'Media requires review'
            reason_admin = 'Media review'
        
        # Add message to database
        message_id = add_message_to_db(
            user_id=user_id,
            university=university,
            message_type=message_type,
            content=caption,
            filtered_content=filtered_caption,
            media_type=media_type,
            file_id=file_id,
            status='pending',
            reason=reason_db
        )
        
        if message_id:
            # Add to moderation queue
            state.moderation_queue[message_id] = {
                'user_id': user_id,
                'media_type': media_type,
                'file_id': file_id,
                'caption': caption,
                'university': university,
                'message_type': message_type,
                'language': language
            }
            
            # Send to all moderators and admins for moderation
            from database import get_moderators
            recipients = set(get_moderators() or [])
            recipients.update(ADMIN_IDS)
            if media_type == 'photo':
                for recipient_id in recipients:
                    try:
                        # Localize buttons for each recipient
                        try:
                            admin_user = get_user(recipient_id)
                            admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                        except Exception:
                            admin_language = 'en'
                        await bot.send_photo(
                            recipient_id,
                            photo=file_id,
                            caption=(
                                f"⚠️ Media for moderation (ID: {message_id})\n\n"
                                f"🏫 University: {university}\n"
                                f"📌 Type: {message_type}\n"
                                f"🔎 Reason: {reason_admin}\n\n"
                                f"📝 Caption:\n{caption}\n\n"
                                f"🧹 Filtered caption:\n{filtered_caption}"
                            ),
                            reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                        )
                    except Exception:
                        pass
            elif media_type == 'video':
                for recipient_id in recipients:
                    try:
                        # Localize buttons for each recipient
                        try:
                            admin_user = get_user(recipient_id)
                            admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                        except Exception:
                            admin_language = 'en'
                        await bot.send_video(
                            recipient_id,
                            video=file_id,
                            caption=(
                                f"⚠️ Media for moderation (ID: {message_id})\n\n"
                                f"🏫 University: {university}\n"
                                f"📌 Type: {message_type}\n"
                                f"🔎 Reason: {reason_admin}\n\n"
                                f"📝 Caption:\n{caption}\n\n"
                                f"🧹 Filtered caption:\n{filtered_caption}"
                            ),
                            reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                        )
                    except Exception:
                        pass
            elif media_type == 'audio':
                for recipient_id in recipients:
                    try:
                        try:
                            admin_user = get_user(recipient_id)
                            admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                        except Exception:
                            admin_language = 'en'
                        await bot.send_audio(
                            recipient_id,
                            audio=file_id,
                            caption=(
                                f"⚠️ Media for moderation (ID: {message_id})\n\n"
                                f"🏫 University: {university}\n"
                                f"📌 Type: {message_type}\n"
                                f"🔎 Reason: {reason_admin}\n\n"
                                f"📝 Caption:\n{caption}\n\n"
                                f"🧹 Filtered caption:\n{filtered_caption}"
                            ) if caption else None,
                            reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                        )
                    except Exception:
                        pass
            elif media_type == 'video_note':
                for recipient_id in recipients:
                    try:
                        try:
                            admin_user = get_user(recipient_id)
                            admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                        except Exception:
                            admin_language = 'en'
                        await bot.send_video_note(
                            recipient_id,
                            video_note=file_id
                        )
                        await bot.send_message(
                            recipient_id,
                            (
                                f"⚠️ Media for moderation (ID: {message_id})\n\n"
                                f"🏫 University: {university}\n"
                                f"📌 Type: {message_type}\n"
                                f"🔎 Reason: {reason_admin}\n\n"
                                f"📝 Caption:\n{caption}\n\n"
                                f"🧹 Filtered caption:\n{filtered_caption}"
                            ),
                            reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                        )
                    except Exception:
                        pass
            else:  # voice
                for recipient_id in recipients:
                    try:
                        try:
                            admin_user = get_user(recipient_id)
                            admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                        except Exception:
                            admin_language = 'en'
                        await bot.send_voice(
                            recipient_id,
                            voice=file_id,
                            caption=(
                                f"⚠️ Media for moderation (ID: {message_id})\n\n"
                                f"🏫 University: {university}\n"
                                f"📌 Type: {message_type}\n"
                                f"🔎 Reason: {reason_admin}\n\n"
                                f"📝 Caption:\n{caption}\n\n"
                                f"🧹 Filtered caption:\n{filtered_caption}"
                            ) if caption else None,
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
                get_text("media_moderation", language),
                reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
            # Clear selection
            try:
                user_data[user_id].pop('message_type', None)
            except Exception:
                pass
        else:
            await message.answer(
                f"{get_text('error', language)} {get_text('when_processing_media', language)}",
                reply_markup=get_user_keyboard(user_id, language)
            )
    
    # Ensure state module is accessible
    state.moderation_queue = state.moderation_queue

    @dp.message(F.poll)
    async def handle_poll_message(message: types.Message):
        user_id = message.from_user.id
        if is_banned(user_id):
            return
        user_data = state.user_data
        user = get_user(user_id)

        # Ensure default university
        if (not user) or (not user[2]) or (user[2] not in UNIVERSITIES):
            language = user[3] if user and user[3] else 'en'
            try:
                from database import add_user
                add_user(user_id, message.from_user.username, 'XIAMEN', language)
            except Exception:
                pass
            user = get_user(user_id)

        language = user[3] if user and user[3] else 'en'

        if user_id not in user_data or 'message_type' not in user_data[user_id]:
            await message.answer(
                get_text("message_type_first", language),
                reply_markup=get_user_keyboard(user_id, language)
            )
            return

        university = user[2]
        message_type = user_data[user_id]['message_type']
        poll = message.poll
        question = poll.question or ""
        options = [opt.text for opt in (poll.options or [])]
        joined_text = (question + "\n" + "\n".join(options)).strip()

        # Minimal words check on question
        if question:
            try:
                words = [w for w in question.split() if w.strip()]
                if len(words) < MIN_MESSAGE_WORDS:
                    await message.answer(
                        get_text('prompts.min_words', language),
                        reply_markup=get_back_keyboard(language)
                    )
                    return
            except Exception:
                pass

        # Analyze for ads/profanity/spam
        has_ads = contains_ad_words(joined_text) if joined_text else False
        has_profanity = contains_banned_words(joined_text) if joined_text else False
        has_spam = contains_spam(joined_text) if joined_text else False
        filtered_question = filter_profanity(question) if has_profanity else question

        if has_ads and has_profanity and has_spam:
            reason_db = 'Ads + Profanity + Spam'
            reason_admin = 'Ad+Profanity+Spam'
        elif has_ads and has_profanity:
            reason_db = 'Ads + Profanity'
            reason_admin = 'Ad+Profanity'
        elif has_ads and has_spam:
            s = spam_score(joined_text)
            reason_db = f'Ads + Spam (score={s:.2f})'
            reason_admin = f'Ad+Spam ({s:.2f})'
        elif has_profanity and has_spam:
            s = spam_score(joined_text)
            reason_db = f'Profanity + Spam (score={s:.2f})'
            reason_admin = f'Profanity+Spam ({s:.2f})'
        elif has_ads:
            reason_db = 'Poll requires review (possible ad)'
            reason_admin = 'Possible ad'
        elif has_spam:
            s = spam_score(joined_text)
            reason_db = f'Poll requires review (spam score={s:.2f})'
            reason_admin = f'Possible spam ({s:.2f})'
        elif has_profanity:
            reason_db = 'Poll requires review (profanity)'
            reason_admin = 'Profanity detected'
        else:
            reason_db = 'Poll requires review'
            reason_admin = 'Poll review'

        # Persist: store question as content, options as file_id (joined), media_type='poll'
        options_blob = "||".join(options)
        message_id = add_message_to_db(
            user_id=user_id,
            university=university,
            message_type=message_type,
            content=question,
            filtered_content=filtered_question,
            media_type='poll',
            file_id=options_blob,
            status='pending',
            reason=reason_db
        )

        if message_id:
            # Add to moderation queue
            state.moderation_queue[message_id] = {
                'user_id': user_id,
                'media_type': 'poll',
                'file_id': options_blob,
                'caption': question,
                'university': university,
                'message_type': message_type,
                'language': language
            }

            # Notify moderators/admins with poll summary
            from database import get_moderators
            recipients = set(get_moderators() or [])
            recipients.update(ADMIN_IDS)
            summary = (
                f"⚠️ Poll for moderation (ID: {message_id})\n\n"
                f"🏫 University: {university}\n"
                f"📌 Type: {message_type}\n"
                f"🔎 Reason: {reason_admin}\n\n"
                f"❓ Question:\n{question}\n\n"
                f"🗳 Options:\n" + "\n".join(f"- {o}" for o in options)
            )
            for recipient_id in recipients:
                try:
                    try:
                        admin_user = get_user(recipient_id)
                        admin_language = admin_user[3] if admin_user and admin_user[3] else 'en'
                    except Exception:
                        admin_language = 'en'
                    await bot.send_message(
                        recipient_id,
                        summary,
                        reply_markup=get_admin_decision_keyboard(message_id, admin_language)
                    )
                except Exception:
                    pass

            # Ack to user
            try:
                from database import is_moderator as _is_moderator
                is_mod = _is_moderator(user_id)
            except Exception:
                is_mod = False
            await message.answer(
                get_text("media_moderation", language),
                reply_markup=get_user_keyboard(user_id, language, is_admin=is_admin(user_id), is_moderator=is_mod)
            )
            try:
                user_data[user_id].pop('message_type', None)
            except Exception:
                pass
        else:
            await message.answer(
                f"{get_text('error', language)} {get_text('when_processing_media', language)}",
                reply_markup=get_user_keyboard(user_id, language)
            )

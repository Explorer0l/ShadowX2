"""
Queue management module for ShadowX Bot
Handles message queue scheduling and processing
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from database import (
    add_message_to_queue,
    get_messages_to_send,
    mark_message_as_sent,
    get_last_scheduled_time,
    get_message,
    count_user_recent_scheduled,
    get_user_recent_scheduled_times,
)
from config import MESSAGE_QUEUE_MIN_INTERVAL, MESSAGE_QUEUE_MAX_INTERVAL, UNIVERSITIES, USER_MAX_PER_HOUR, USER_RATE_WINDOW_SECONDS
from utils.translate import maybe_augment_with_english
from aiogram.exceptions import TelegramRetryAfter, TelegramServerError, TelegramNetworkError, TelegramBadRequest, TelegramForbiddenError

class MessageQueue:
    def __init__(self, bot):
        """Initialize the message queue manager"""
        self.bot = bot
        self.task = None
        self.is_running = False
    
    async def start(self):
        """Start the queue processing task"""
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self.process_queue())
    
    async def stop(self):
        """Stop the queue processing task"""
        if self.is_running and self.task:
            self.is_running = False
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
    
    def schedule_message(self, message_id):
        """Schedule a message to be sent as soon as allowed by per-user hourly limit.
        Removes global delay. If the user reached the hourly cap, schedule at the
        earliest allowed time when a slot opens (rolling window of 1 hour).
        """
        now = datetime.now()
        window_seconds = int(USER_RATE_WINDOW_SECONDS) if int(USER_RATE_WINDOW_SECONDS) > 0 else 3600
        try:
            msg_row = get_message(int(message_id))
        except Exception:
            msg_row = None
        # Default: schedule now if can't resolve user
        scheduled_dt = now
        if msg_row:
            try:
                user_id = int(msg_row[1])
            except Exception:
                user_id = None
            if USER_MAX_PER_HOUR and USER_MAX_PER_HOUR > 0 and user_id:
                try:
                    recent_count = count_user_recent_scheduled(user_id, window_seconds=window_seconds)
                    if recent_count >= int(USER_MAX_PER_HOUR):
                        # Compute earliest slot: oldest scheduled within window + window_seconds + 1s
                        times = get_user_recent_scheduled_times(user_id, window_seconds=window_seconds)
                        if times:
                            oldest = min(times)
                            candidate = oldest + timedelta(seconds=window_seconds + 1)
                            if candidate > scheduled_dt:
                                scheduled_dt = candidate
                        # Inform user about the wait time in English
                        try:
                            remaining = int(max(1, (scheduled_dt - now).total_seconds()))
                            hours, rem = divmod(remaining, 3600)
                            minutes, seconds = divmod(rem, 60)
                            parts = []
                            if hours:
                                parts.append(f"{hours}h")
                            if minutes:
                                parts.append(f"{minutes}m")
                            # Always show seconds to be precise
                            parts.append(f"{seconds}s")
                            wait_str = " ".join(parts)
                            note = (
                                "You have reached your hourly posting limit.\n"
                                f"Your message has been scheduled and will be posted in {wait_str}."
                            )
                            # Send as a best-effort notification; ignore failures
                            try:
                                import asyncio as _asyncio
                                _asyncio.create_task(self.bot.send_message(chat_id=user_id, text=note))
                            except Exception:
                                try:
                                    import asyncio as _asyncio
                                    _asyncio.get_event_loop().create_task(self.bot.send_message(chat_id=user_id, text=note))
                                except Exception:
                                    # Last resort: skip silently
                                    pass
                        except Exception:
                            pass
                except Exception:
                    # On any error, fall back to scheduling now
                    pass
        # Always ensure we don't schedule in the past
        if scheduled_dt < now:
            scheduled_dt = now
        scheduled_time = scheduled_dt.strftime('%Y-%m-%d %H:%M:%S')
        add_message_to_queue(message_id, scheduled_time)
    
    async def process_queue(self):
        """Process the message queue continuously"""
        while self.is_running:
            try:
                # Get messages that are ready to be sent
                messages = get_messages_to_send()
                
                for queue_id, message_id, user_id, university, message_type, content, filtered_content, media_type, file_id, status, reason, timestamp in messages:
                    try:
                        # Get channel for this university
                        channel = UNIVERSITIES.get(university)
                        if not channel:
                            continue
                        
                        # Check if we need to use filtered content
                        send_content = filtered_content if filtered_content else content
                        # Optionally augment with English translation (Original/English) for non-poll content
                        try:
                            if send_content and (not media_type or media_type != 'poll'):
                                send_content = await maybe_augment_with_english(send_content)
                        except Exception:
                            # If translation fails, proceed with original content
                            logging.debug("Translation step failed; using original text", exc_info=True)
                        
                        # Get message number for this university
                        from database import get_message_counter
                        message_number = get_message_counter(university)
                        
                        # Get language for this user (English-only default)
                        from database import get_user
                        user = get_user(user_id)
                        language = user[3] if user else 'en'
                        
                        # Get hashtag for message type by matching literal label
                        from config import MESSAGE_TYPES
                        hashtag = MESSAGE_TYPES.get(message_type, "")
                        
                        # Format the final message
                        if media_type:
                            # For media posts
                            if media_type == 'album':
                                # Parse album items (only photo/video are supported in albums)
                                try:
                                    from aiogram.types import InputMediaPhoto, InputMediaVideo
                                    items = []
                                    for token in (file_id or '').split('||'):
                                        if not token:
                                            continue
                                        try:
                                            t, mid = token.split(':', 1)
                                        except ValueError:
                                            continue
                                        if t == 'photo':
                                            items.append(('photo', mid))
                                        elif t == 'video':
                                            items.append(('video', mid))
                                    # Build caption
                                    if send_content:
                                        final_caption = f"{send_content}\n№{message_number}"
                                    else:
                                        final_caption = f"№{message_number}"
                                    if hashtag:
                                        final_caption = f"{hashtag}\n{final_caption}\n{hashtag}"
                                    media_group = []
                                    for idx, (t, mid) in enumerate(items):
                                        cap = final_caption if idx == 0 else None
                                        if t == 'photo':
                                            media_group.append(InputMediaPhoto(media=mid, caption=cap))
                                        elif t == 'video':
                                            media_group.append(InputMediaVideo(media=mid, caption=cap))
                                    if media_group:
                                        try:
                                            await self.bot.send_media_group(chat_id=channel, media=media_group)
                                        except TelegramRetryAfter as e:
                                            await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                            continue
                                        except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                            logging.warning("Transient error sending album; retrying soon", exc_info=True)
                                            await asyncio.sleep(2)
                                            continue
                                    else:
                                        # Fallback: if no valid items, skip
                                        logging.warning(f"Album message {message_id} has no valid items")
                                        mark_message_as_sent(queue_id)
                                        continue
                                except Exception:
                                    logging.exception("Error preparing album; skipping")
                                    mark_message_as_sent(queue_id)
                                    continue
                            elif media_type == 'photo':
                                try:
                                    await self.bot.send_photo(
                                        chat_id=channel,
                                        photo=file_id,
                                        caption=(f"{hashtag}\n{send_content}\n№{message_number}\n{hashtag}" if (hashtag and send_content) else (f"{send_content}\n№{message_number}" if send_content else (f"{hashtag}\n№{message_number}\n{hashtag}" if hashtag else f"№{message_number}")))
                                    )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending photo; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                            elif media_type == 'video':
                                try:
                                    await self.bot.send_video(
                                        chat_id=channel,
                                        video=file_id,
                                        caption=(f"{hashtag}\n{send_content}\n№{message_number}\n{hashtag}" if (hashtag and send_content) else (f"{send_content}\n№{message_number}" if send_content else (f"{hashtag}\n№{message_number}\n{hashtag}" if hashtag else f"№{message_number}")))
                                    )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending video; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                            elif media_type == 'audio':
                                try:
                                    await self.bot.send_audio(
                                        chat_id=channel,
                                        audio=file_id,
                                        caption=((f"{hashtag}\n{send_content}\n№{message_number}\n{hashtag}" if hashtag else f"{send_content}\n№{message_number}") if send_content else None)
                                    )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending audio; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                            elif media_type == 'voice':
                                try:
                                    await self.bot.send_voice(
                                        chat_id=channel,
                                        voice=file_id,
                                        caption=((f"{hashtag}\n{send_content}\n№{message_number}\n{hashtag}" if hashtag else f"{send_content}\n№{message_number}") if send_content else None)
                                    )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending voice; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                            elif media_type == 'video_note':
                                try:
                                    # Video notes cannot have captions
                                    await self.bot.send_video_note(
                                        chat_id=channel,
                                        video_note=file_id
                                    )
                                    # Send a separate message with caption/number and hashtags if needed
                                    # Build caption text similar to other media
                                    if send_content:
                                        extra_text = f"{send_content}\n№{message_number}"
                                    else:
                                        extra_text = f"№{message_number}"
                                    if hashtag:
                                        extra_text = f"{hashtag}\n{extra_text}\n{hashtag}"
                                    if extra_text:
                                        await self.bot.send_message(
                                            chat_id=channel,
                                            text=extra_text
                                        )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending video note; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                            elif media_type == 'poll':
                                # file_id contains options joined by '||'
                                try:
                                    from config import POLL_IS_ANONYMOUS, POLL_ALLOWS_MULTIPLE
                                    options = (file_id or "").split('||') if file_id else []
                                    # Send native poll with question=send_content or fallback, append order number
                                    base_question = (send_content or '').strip() or 'Poll'
                                    question = f"{base_question} \u2116{message_number}" if base_question else f"\u2116{message_number}"
                                    # Telegram requires 2-10 options
                                    safe_options = [o for o in options if o.strip()][:10]
                                    if len(safe_options) < 2:
                                        safe_options = ["Yes", "No"]
                                    try:
                                        await self.bot.send_poll(
                                            chat_id=channel,
                                            question=question,
                                            options=safe_options,
                                            allows_multiple_answers=bool(POLL_ALLOWS_MULTIPLE),
                                            is_anonymous=bool(POLL_IS_ANONYMOUS)
                                        )
                                    except TelegramBadRequest as e:
                                        # Channels запрещают неанонимные опросы: попробуем анонимно
                                        if 'non-anonymous polls can\'t be sent to channel chats' in str(e).lower():
                                            await asyncio.sleep(0)
                                            await self.bot.send_poll(
                                                chat_id=channel,
                                                question=question,
                                                options=safe_options,
                                                allows_multiple_answers=bool(POLL_ALLOWS_MULTIPLE),
                                                is_anonymous=True
                                            )
                                        else:
                                            raise
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending poll; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                        else:
                            # For text posts
                            final_message = f"{hashtag}\n{send_content}\n№{message_number}\n{hashtag}" if hashtag else f"{send_content}\n№{message_number}"
                            try:
                                await self.bot.send_message(
                                    chat_id=channel,
                                    text=final_message
                                )
                            except TelegramRetryAfter as e:
                                await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                continue
                            except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                logging.warning("Transient error sending message; retrying soon", exc_info=True)
                                await asyncio.sleep(2)
                                continue
                        
                        # Persist published mapping (university, number -> original user/message)
                        try:
                            from database import save_published_mapping
                            save_published_mapping(university, message_number, message_id, user_id)
                        except Exception:
                            logging.debug("Failed to save published mapping", exc_info=True)

                        # Mark as sent
                        mark_message_as_sent(queue_id)
                        
                        # Let the user know their message was published
                        try:
                            from handlers.language import get_text
                            if media_type:
                                notification = get_text('media_published', language).format(number=message_number)
                            else:
                                notification = get_text('message_published', language).format(number=message_number)
                            await self.bot.send_message(
                                chat_id=user_id,
                                text=notification
                            )
                        except Exception:
                            logging.warning(f"Failed to notify user {user_id}", exc_info=True)
                        
                    except TelegramForbiddenError as e:
                        # Non-retryable: bot not a member or posting not allowed
                        logging.error(
                            f"Forbidden while posting to {university} ({channel}). "
                            f"Ensure bot is added as an admin to the channel. Message {message_id} will be marked failed."
                        )
                        try:
                            from database import mark_message_as_failed
                            mark_message_as_failed(queue_id)
                        except Exception:
                            logging.debug("Failed to mark message as failed", exc_info=True)
                        # Optionally notify user that posting failed
                        try:
                            await self.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "Your message couldn't be posted because the bot is not a member of the channel. "
                                    "Please try again later."
                                )
                            )
                        except Exception:
                            pass
                        continue
                    except Exception:
                        logging.exception(f"Error processing queued message {message_id}")
                
                # If nothing to send, sleep a bit longer to reduce CPU
                await asyncio.sleep(0 if messages else 2)
            
            except Exception:
                logging.exception("Queue processing error")
                await asyncio.sleep(5)  # Wait a bit on error

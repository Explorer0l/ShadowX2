"""
Queue management module for ShadowX Bot
Handles message queue scheduling and processing
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from database import add_message_to_queue, get_messages_to_send, mark_message_as_sent, get_last_scheduled_time
from config import MESSAGE_QUEUE_MIN_INTERVAL, MESSAGE_QUEUE_MAX_INTERVAL, UNIVERSITIES
from aiogram.exceptions import TelegramRetryAfter, TelegramServerError, TelegramNetworkError

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
        """Schedule a message to be sent later, spaced by configured interval range."""
        now = datetime.now()
        last_time = get_last_scheduled_time()
        # Choose random interval in configured range
        spacing = random.randint(MESSAGE_QUEUE_MIN_INTERVAL, MESSAGE_QUEUE_MAX_INTERVAL)
        if last_time and last_time > now:
            next_time = last_time + timedelta(seconds=spacing)
        else:
            next_time = now + timedelta(seconds=spacing)
        scheduled_time = next_time.strftime('%Y-%m-%d %H:%M:%S')
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
                        
                        # Get message number for this university
                        from database import get_message_counter
                        message_number = get_message_counter(university)
                        
                        # Get language for this user
                        from database import get_user
                        user = get_user(user_id)
                        language = user[3] if user else 'ru'
                        
                        # Get hashtag for message type by matching literal label
                        from config import MESSAGE_TYPES
                        hashtag = ""
                        for lang_code in ("ru", "en"):
                            tags = MESSAGE_TYPES.get(lang_code, {})
                            if message_type in tags:
                                hashtag = tags[message_type]
                                break
                        
                        # Format the final message
                        if media_type:
                            # For media posts
                            if send_content:
                                final_caption = f"{send_content}\n№{message_number}"
                            else:
                                final_caption = f"№{message_number}"
                            
                            # Add hashtags if needed
                            if hashtag:
                                final_caption = f"{hashtag}\n{final_caption}\n{hashtag}"
                            
                            if media_type == 'photo':
                                try:
                                    await self.bot.send_photo(
                                        chat_id=channel,
                                        photo=file_id,
                                        caption=final_caption
                                    )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending photo; retrying soon", exc_info=True)
                                    await asyncio.sleep(2)
                                    continue
                            else:  # video
                                try:
                                    await self.bot.send_video(
                                        chat_id=channel,
                                        video=file_id,
                                        caption=final_caption
                                    )
                                except TelegramRetryAfter as e:
                                    await asyncio.sleep(int(getattr(e, 'retry_after', 5)) + 1)
                                    continue
                                except (TelegramServerError, TelegramNetworkError, asyncio.TimeoutError):
                                    logging.warning("Transient error sending video; retrying soon", exc_info=True)
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
                        
                    except Exception:
                        logging.exception(f"Error processing queued message {message_id}")
                
                # Pace checking lightly; sending itself is paced by scheduled_time
                await asyncio.sleep(1)
            
            except Exception:
                logging.exception("Queue processing error")
                await asyncio.sleep(5)  # Wait a bit on error

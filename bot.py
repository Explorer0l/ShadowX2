"""
Main entry point for the ShadowX Bot
Initializes the bot and registers all handlers
"""

import asyncio
import os, sys
import logging
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import TOKEN
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramUnauthorizedError

# Configure logging
logging.basicConfig(level=logging.INFO)

# Dispatcher can be created at import; Bot/session must be created within a running loop
dp = Dispatcher()
bot = None  # will be initialized in main()

# Import database initialization
# Ensure project root is on sys.path for reliable local imports
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from database import init_db

# Import handlers modules
from handlers.language import register_language_handlers
from handlers.messages import register_message_handlers
from handlers.media import register_media_handlers
from handlers.moderation import register_moderation_handlers

async def on_startup():
    """Actions to perform when the bot starts"""
    # Initialize the database
    init_db()
    # Register bot commands (English-only)
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Start"),
            BotCommand(command="help", description="Help"),
        ])
    except Exception:
        logging.exception("Failed to set bot commands")
    logging.info("Bot has been started!")

async def on_shutdown():
    """Actions to perform when the bot stops"""
    try:
        # Stop message queue if it exists
        import state
        if state.queue_manager:
            await state.queue_manager.stop()
        
        # Properly close the bot session
        if bot is not None and getattr(bot, 'session', None) is not None:
            try:
                await bot.session.close()
            except Exception:
                logging.debug("Error while closing bot session", exc_info=True)
        logging.info("Bot session closed cleanly")

        # Close database connection pool gracefully
        try:
            from utils.db_pool import get_db_pool
            try:
                get_db_pool().close_all()
                logging.info("Database pool closed cleanly")
            except Exception:
                logging.debug("Error while closing DB pool", exc_info=True)
        except Exception:
            logging.debug("DB pool not available to close", exc_info=True)
        
        logging.info("Bot has been stopped!")
    except Exception:
        logging.exception("Error during shutdown")

async def register_handlers():
    """Register all handlers from modules"""
    await register_language_handlers(dp, bot)
    await register_media_handlers(dp, bot)
    await register_moderation_handlers(dp, bot)
    await register_message_handlers(dp, bot)  # Register message handlers last to avoid conflicts

async def main():
    """Main function to start the bot"""
    try:
        # Initialize tuned HTTP session and bot inside running loop
        global bot
        # Use numeric timeout (seconds) to match aiogram expectations
        session = AiohttpSession(timeout=30)
        bot = Bot(token=TOKEN, session=session)

        # Verify token early to provide a clear error
        try:
            me = await bot.get_me()
            logging.info(f"Authorized as @{getattr(me, 'username', '')} id={getattr(me, 'id', '')}")
        except TelegramUnauthorizedError:
            logging.error("Unauthorized: BOT_TOKEN is invalid or revoked. Set a valid token in .env (BOT_TOKEN=...) and restart.")
            return

        # Call on_startup
        await on_startup()
        
        # Clean up any existing webhook
        logging.info("Cleaning up webhook…")
        await bot.delete_webhook(drop_pending_updates=True)
        logging.info("Webhook cleaned up successfully!")
        
        # Register all handlers
        await register_handlers()
        
        # Start polling with clean updates
        logging.info("Starting bot…")
        # Poll only essential updates to reduce load
        allowed_updates = ["message", "callback_query"]
        # Optimized polling settings for high load
        await dp.start_polling(
            bot, 
            skip_updates=True, 
            allowed_updates=allowed_updates
        )
    except Exception:
        logging.exception("Fatal error in main loop")
    finally:
        # Call on_shutdown at the end
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())

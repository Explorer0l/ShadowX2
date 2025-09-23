"""
More aggressive script to clear Telegram bot session
For when regular reset_webhook.py doesn't work
"""

import asyncio
import sys
import time
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from config import TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def clear_telegram_session():
    """Clear Telegram session with multiple attempts"""
    bot = Bot(token=TOKEN)
    success = False
    
    try:
        # First try: Delete webhook
        logger.info("Step 1: Deleting webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully")
        
        # Second try: Get bot info to verify connection
        logger.info("Step 2: Testing bot connection...")
        me = await bot.get_me()
        logger.info(f"Connection successful. Bot name: {me.full_name}")
        
        # Third try: Get updates with offset to clear queue
        logger.info("Step 3: Clearing update queue...")
        updates = await bot.get_updates(offset=-1, limit=1)
        if updates:
            last_update_id = updates[-1].update_id
            logger.info(f"Last update ID: {last_update_id}")
            # Clear all updates up to the latest one
            await bot.get_updates(offset=last_update_id + 1)
            logger.info("Update queue cleared")
        else:
            logger.info("No pending updates found")
        
        success = True
        logger.info("✅ Bot session cleared successfully!")
    except TelegramAPIError as telegram_error:
        logger.error(f"Telegram API error: {telegram_error}")
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
    finally:
        # Make sure to close the session
        try:
            await bot.session.close()
            logger.info("Bot session closed")
        except Exception as e:
            logger.error(f"Error closing session: {e}")
    
    return success

if __name__ == "__main__":
    # Try multiple times with delay
    max_attempts = 3
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        print(f"\nAttempt {attempt}/{max_attempts}:")
        
        success = asyncio.run(clear_telegram_session())
        
        if success:
            print("\n✅ Session cleared successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Failed to clear session on attempt {attempt}")
            if attempt < max_attempts:
                wait_time = 5
                print(f"Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
    
    print("\n❌ Failed to clear session after multiple attempts")
    sys.exit(1)

"""
Script to reset the webhook for your bot
Run this if you encounter TelegramConflictError
"""

import asyncio
import sys
from aiogram import Bot
from config import TOKEN

async def reset_webhook():
    """Reset the webhook and drop pending updates"""
    try:
        bot = Bot(token=TOKEN)
        print("Resetting webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook successfully reset!")
        
        # Close bot session properly
        await bot.session.close()
        
        return True
    except Exception as e:
        print(f"❌ Error resetting webhook: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(reset_webhook())
    sys.exit(0 if success else 1)

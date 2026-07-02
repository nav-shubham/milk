import os
import sys
import asyncio
from dotenv import load_dotenv

# Allow importing from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.bot import build_application

async def set_webhook():
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        print("❌ Error: WEBHOOK_URL is not set in your .env file.")
        print("Please set WEBHOOK_URL=https://<your-username>.pythonanywhere.com in your .env")
        return
        
    bot_token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("❌ Error: BOT_TOKEN is not set in your .env file.")
        return

    # Remove trailing slash
    webhook_url = webhook_url.rstrip("/")
    full_url = f"{webhook_url}/webhook/{bot_token}"
    
    app = build_application()
    
    print(f"Connecting to Telegram and setting Webhook URL to:\n👉 {full_url}\n")
    
    try:
        await app.initialize()
        success = await app.bot.set_webhook(url=full_url)
        if success:
            print("✅ Webhook set successfully!")
            print("You can now configure your PythonAnywhere Web App using this project.")
        else:
            print("❌ Telegram rejected setting the webhook. Check your token and URL.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(set_webhook())

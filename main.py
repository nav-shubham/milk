import os
import sys
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Flask, request, jsonify
from telegram import Update

# Setup logging before importing other modules
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "milk_bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, maxBytes=1024 * 1024 * 5, backupCount=5, encoding="utf-8")
    ]
)
logger = logging.getLogger("main")

# Auto-run DB initialization script to ensure DB and tables are present
from scripts.init_db import init_db
try:
    init_db()
except Exception as e:
    logger.critical(f"Failed to initialize database: {e}", exc_info=True)
    sys.exit(1)

from app.bot import build_application
from app.config import BOT_TOKEN, ADMIN_TELEGRAM_IDS

# Build Telegram Bot Application
application = build_application()

# Initialize Flask App (for Webhook deployment, e.g. Free PythonAnywhere accounts)
flask_app = Flask(__name__)

# Initialize the PTB application event loop once
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())

@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Endpoint for Telegram Webhook updates."""
    try:
        update_data = request.get_json()
        if update_data:
            update = Update.de_json(update_data, application.bot)
            loop.run_until_complete(application.process_update(update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}", exc_info=True)
        return "Error", 500

@flask_app.route("/", methods=["GET"])
def index():
    """Health check endpoint."""
    return jsonify({"status": "running", "mode": "webhook"}), 200

def main():
    logger.info("Starting Telegram Milk Billing Bot in POLLING mode...")
    logger.info(f"Loaded Admin Telegram IDs: {ADMIN_TELEGRAM_IDS}")
    
    try:
        # Start the bot using polling method
        logger.info("Bot starting polling loop...")
        application.run_polling()
    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

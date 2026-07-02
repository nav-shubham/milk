import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Core Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID_STR = os.getenv("ADMIN_TELEGRAM_ID") or os.getenv("TELEGRAM_CHAT_ID")

# Admin IDs can be a single ID or a list of IDs. We store it as a list of integers.
ADMIN_TELEGRAM_IDS = []
if ADMIN_TELEGRAM_ID_STR:
    # Support comma-separated admin IDs
    for admin_id in ADMIN_TELEGRAM_ID_STR.split(","):
        admin_id = admin_id.strip()
        if admin_id.isdigit():
            ADMIN_TELEGRAM_IDS.append(int(admin_id))
        elif admin_id.startswith("-") and admin_id[1:].isdigit(): # Negative IDs (chat/group IDs)
            ADMIN_TELEGRAM_IDS.append(int(admin_id))

DEFAULT_RATE = float(os.getenv("DEFAULT_RATE", "65.0"))

# Database path (relative to project root if not absolute)
db_path_str = os.getenv("DATABASE_PATH", "data/milk.db")
DATABASE_PATH = Path(db_path_str)
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH

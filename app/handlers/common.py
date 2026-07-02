import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from app.config import ADMIN_TELEGRAM_IDS

logger = logging.getLogger(__name__)

def admin_only(func):
    """Decorator to restrict handler execution to admin users only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            logger.warning("Received an update without a valid user.")
            return
            
        if user.id not in ADMIN_TELEGRAM_IDS:
            logger.warning(
                f"Unauthorized admin action attempt: User ID {user.id} "
                f"({user.username or 'No Username'}) tried to run {func.__name__}."
            )
            # Notify the user that this command is restricted
            await update.effective_message.reply_text("⛔ This command is restricted to the administrator.")
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapper

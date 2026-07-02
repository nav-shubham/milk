import logging
from telegram import BotCommand
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import BOT_TOKEN
from app.handlers import user, admin

logger = logging.getLogger(__name__)

async def post_init(application: Application) -> None:
    """Sets the list of bot commands in Telegram for autocomplete / command menu."""
    commands = [
        BotCommand("start", "Start the bot and see welcome message"),
        BotCommand("help", "Show all available commands"),
        BotCommand("rate", "Show the milk rate applicable today"),
        BotCommand("entry", "Record milk quantity: /entry <liters> [date]"),
        BotCommand("today", "Show today's recorded milk entry"),
        BotCommand("entries", "Show the last 10 milk entries"),
        BotCommand("bill", "Calculate bill: /bill [dates|list] or /bill [start] [end]"),
        BotCommand("history", "Show billing cycle history"),
        BotCommand("report", "Show billing summary: /report [dates] or /report [start] [end]"),
        BotCommand("setrate", "Admin: Set milk rate: /setrate <rate> [date]"),
        BotCommand("close", "Admin: Close cycle/range: /close [start] [end]"),
        BotCommand("delete", "Admin: Delete entry: /delete [date]")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot autocomplete commands configured.")

def build_application() -> Application:
    """Builds and configures the Telegram Bot application."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN (or TELEGRAM_BOT_TOKEN) environment variable is not set.")

    # Build python-telegram-bot application with post_init
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Register Admin Commands
    application.add_handler(CommandHandler("setrate", admin.set_rate_handler))
    application.add_handler(CommandHandler("close", admin.close_cycle_handler))
    application.add_handler(CommandHandler("delete", admin.delete_handler))

    # Register User Commands
    application.add_handler(CommandHandler("start", user.start_handler))
    application.add_handler(CommandHandler("help", user.help_handler))
    application.add_handler(CommandHandler("rate", user.rate_handler))
    application.add_handler(CommandHandler("entry", user.entry_handler))
    application.add_handler(CommandHandler("today", user.today_handler))
    application.add_handler(CommandHandler("entries", user.entries_handler))
    application.add_handler(CommandHandler("bill", user.bill_handler))
    application.add_handler(CommandHandler("history", user.history_handler))
    application.add_handler(CommandHandler("report", user.report_handler))

    # Register Callback Query Handler (e.g., /delete confirmation inline buttons)
    application.add_handler(CallbackQueryHandler(admin.delete_callback_handler))

    # Register Plain Text Number Entry Handler
    # Matches integers or decimal numbers with optional date (e.g., "10" or "12.5" or "10 2026-06-13")
    application.add_handler(
        MessageHandler(
            filters.TEXT & (~filters.COMMAND) & filters.Regex(r'^\d+(\.\d+)?(?:\s+\d{4}-\d{2}-\d{2})?$'),
            user.plain_number_handler
        )
    )

    logger.info("Application handlers registered successfully.")
    return application

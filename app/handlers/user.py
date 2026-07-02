import logging
from datetime import date, datetime
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from app.services import db_service

logger = logging.getLogger(__name__)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start. Greets the user and lists available commands."""
    user = update.effective_user
    username = user.first_name if user else "there"
    
    welcome_text = (
        f"👋 Hello {username}!\n\n"
        "Welcome to the *Milk Billing Bot*. I will help you track daily milk deliveries "
        "and calculate billing cycles.\n\n"
        "📖 Use /help to see all available commands."
    )
    await update.effective_message.reply_text(welcome_text, parse_mode="Markdown")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help. Shows all available commands for users and admins."""
    help_text = (
        "🥛 *Milk Billing Bot Commands*\n\n"
        "📌 *User Commands:*\n"
        "• `/rate` - Show current milk rate\n"
        "• `/entry <liters> [YYYY-MM-DD]` - Record milk (defaults to today). If entry already exists, it modifies it.\n"
        "• `/today` - View today's milk entry\n"
        "• `/entries` - View recent entries (last 10)\n"
        "• `/bill [dates|list]` or `/bill [start_date] [end_date]` - Calculate bill\n"
        "• `/history` - View billing cycle history\n"
        "• `/report [dates|list]` or `/report [start_date] [end_date]` - Generate summary report\n"
        "• `/help` - Show this help message\n\n"
        "⚙️ *Admin Commands:* (restricted)\n"
        "• `/setrate <rate> [YYYY-MM-DD]` - Set rate (defaults to starting today)\n"
        "• `/close [start_date] [end_date]` - Mark current cycle or a date range as PAID\n"
        "• `/delete [YYYY-MM-DD]` - Delete the latest or a specific past entry (requires confirmation)"
    )
    await update.effective_message.reply_text(help_text, parse_mode="Markdown")

async def rate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /rate. Shows the rate applicable today."""
    try:
        current_rate = db_service.get_current_rate()
        await update.effective_message.reply_text(f"🥛 Current Milk Rate: *₹{current_rate:.2f}/L*", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in rate_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to retrieve current rate.")

async def add_milk_entry_logic(update: Update, liters_val: float, date_str: Optional[str] = None):
    """Common logic to record milk entry for a specific date (defaults to today)."""
    try:
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
        else:
            # Validate date format
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                await update.effective_message.reply_text("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2026-06-13).")
                return

        # Find the correct cycle for the date
        cycle = db_service.get_cycle_for_date(date_str)
        cycle_id = cycle["id"]
        cycle_number = cycle["cycle_number"]
        cycle_status = cycle["status"]
        
        # Check if entry already exists (for modification message)
        existing = db_service.get_today_entry(date_str)
        
        # Record entry (this will overwrite if the date already has an entry)
        entry = db_service.create_milk_entry(date_str, liters_val, cycle_id)
        
        warning_msg = ""
        if cycle_status == "PAID":
            warning_msg = "\n\n⚠️ *Note:* This entry was added to a cycle that is already closed/paid."

        action = "Updated" if existing else "Added"
        val_change = f"🥛 Milk: {existing['liters']}L ➔ {entry['liters']}L" if existing else f"🥛 Milk: {entry['liters']}L"

        response = (
            f"✅ *Milk Entry {action}*\n\n"
            f"📅 Date: {entry['entry_date']}\n"
            f"{val_change}\n"
            f"📦 Cycle: {cycle_number}{warning_msg}"
        )
        await update.effective_message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error adding milk entry: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to add milk entry. Please check logs.")

async def entry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /entry <liters> [date]."""
    if not context.args:
        await update.effective_message.reply_text(
            "ℹ️ *Milk Entry Usage:*\n\n"
            "To record today's milk, copy, edit, and send this:\n"
            "`/entry 10`\n\n"
            "To record milk for a specific date, copy, edit, and send this:\n"
            "`/entry 10 2026-06-13`\n\n"
            "💡 *Tip:* You can also simply send just the numbers (e.g. `10` or `10 2026-06-13`) without typing `/entry`!",
            parse_mode="Markdown"
        )
        return
        
    try:
        liters_val = float(context.args[0])
        if liters_val <= 0:
            await update.effective_message.reply_text("❌ Quantity must be a positive number.")
            return
    except ValueError:
        await update.effective_message.reply_text("❌ Invalid quantity. Please enter a valid number (e.g., 10 or 12.5).")
        return
        
    date_str = None
    if len(context.args) >= 2:
        date_str = context.args[1]
        
    await add_milk_entry_logic(update, liters_val, date_str)

async def plain_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intercepts plain number messages and treats them as /entry <number> [date]."""
    text = update.effective_message.text.strip()
    parts = text.split()
    if not parts:
        return
        
    try:
        liters_val = float(parts[0])
        if liters_val <= 0:
            await update.effective_message.reply_text("❌ Quantity must be a positive number.")
            return
    except ValueError:
        return
        
    date_str = parts[1] if len(parts) >= 2 else None
    await add_milk_entry_logic(update, liters_val, date_str)

async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /today. Shows today's milk entry if it exists."""
    try:
        today_str = date.today().strftime("%Y-%m-%d")
        entry = db_service.get_today_entry(today_str)
        
        if not entry:
            await update.effective_message.reply_text(f"ℹ️ No milk entry recorded for today ({today_str}).")
            return
            
        open_cycle = db_service.get_open_cycle()
        
        response = (
            "🥛 *Today's Milk Entry*\n\n"
            f"📅 Date: {entry['entry_date']}\n"
            f"🥛 Quantity: {entry['liters']}L\n"
            f"📦 Cycle: {open_cycle['cycle_number']}"
        )
        await update.effective_message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in today_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to retrieve today's entry.")

async def entries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /entries. Displays recent 10 milk entries."""
    try:
        entries = db_service.get_recent_entries(limit=10)
        if not entries:
            await update.effective_message.reply_text("ℹ️ No milk entries recorded yet.")
            return
            
        msg = "📅 *Recent Entries (Last 10)*\n\n"
        for entry in entries:
            msg += f"• *{entry['entry_date']}*: {entry['liters']}L (Cycle {entry['cycle_number']})\n"
            
        await update.effective_message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in entries_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to retrieve recent entries.")

async def bill_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /bill [dates|list] or /bill [start_date] [end_date].
    Calculates bill details.
    """
    try:
        show_dates = False
        start_date = None
        end_date = None
        
        if context.args:
            arg0 = context.args[0].lower()
            if arg0 in ("dates", "list"):
                show_dates = True
                if len(context.args) >= 2:
                    start_date = context.args[1]
                    end_date = context.args[2] if len(context.args) >= 3 else date.today().strftime("%Y-%m-%d")
            else:
                start_date = context.args[0]
                end_date = context.args[1] if len(context.args) >= 2 else date.today().strftime("%Y-%m-%d")
                show_dates = True  # Always show dates for custom ranges
                
        # Validate dates if specified
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                await update.effective_message.reply_text(
                    "❌ Invalid date format. Please use YYYY-MM-DD.\n"
                    "Usage: `/bill` or `/bill dates` or `/bill 2026-06-01` or `/bill 2026-06-01 2026-06-15`",
                    parse_mode="Markdown"
                )
                return

        if start_date:
            bill_info = db_service.get_bill_for_range(start_date, end_date)
            entries = bill_info["entries"]
            total_liters = bill_info["total_liters"]
            bill_amount = bill_info["bill_amount"]
            
            response = (
                f"📅 *Bill for Range:* {start_date} to {end_date}\n\n"
                f"🥛 Total Milk: *{total_liters}L*\n"
                f"💵 *Bill Amount: ₹{bill_amount:,.2f}*\n\n"
            )
            
            if show_dates and entries:
                response += "*Entries Breakdown:*\n"
                for e in entries:
                    response += f"• {e['entry_date']}: {e['liters']}L @ ₹{e['rate']:.1f}/L = ₹{e['cost']:.1f} (Cycle {e['cycle_number']})\n"
                    
            await update.effective_message.reply_text(response, parse_mode="Markdown")
        else:
            open_cycle = db_service.get_open_cycle()
            cycle_id = open_cycle["id"]
            cycle_number = open_cycle["cycle_number"]
            
            bill_info = db_service.get_cycle_bill(cycle_id)
            entries = bill_info["entries"]
            total_liters = bill_info["total_liters"]
            bill_amount = bill_info["bill_amount"]
            
            current_rate = db_service.get_current_rate()
            
            response = f"📦 *Current Cycle:* {cycle_number}\n\n"
            response += f"🥛 Total Milk: *{total_liters}L*\n"
            
            rates_in_cycle = sorted(list(set(e["rate"] for e in entries)))
            if len(rates_in_cycle) <= 1:
                rate_val = rates_in_cycle[0] if rates_in_cycle else current_rate
                response += f"💰 Rate: *₹{rate_val:.2f}/L*\n\n"
            else:
                response += f"💰 Current Rate: *₹{current_rate:.2f}/L*\n\n"
                response += "*Rate Summary:*\n"
                grouped_rates = {}
                for e in entries:
                    r = e["rate"]
                    grouped_rates[r] = grouped_rates.get(r, 0.0) + e["liters"]
                for r, l in sorted(grouped_rates.items()):
                    response += f"• {l}L @ ₹{r:.2f}/L = ₹{l*r:,.2f}\n"
                response += "\n"
                
            response += f"💵 *Bill Amount: ₹{bill_amount:,.2f}*"
            
            if show_dates and entries:
                response += "\n\n*Entries Breakdown:*\n"
                for e in entries:
                    response += f"• {e['entry_date']}: {e['liters']}L @ ₹{e['rate']:.1f}/L = ₹{e['cost']:.1f}\n"
                    
            await update.effective_message.reply_text(response, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in bill_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to calculate bill.")

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /history. Shows billing cycle history."""
    try:
        history = db_service.get_cycle_history()
        if not history:
            await update.effective_message.reply_text("ℹ️ No billing history available.")
            return
            
        msg = "📋 *Billing Cycle History*\n\n"
        for item in history:
            status_emoji = "🟢" if item["status"] == "OPEN" else "✅"
            status_text = "Open" if item["status"] == "OPEN" else "Paid"
            msg += f"• Cycle {item['cycle_number']} - {status_emoji} {status_text} - *₹{item['billed_amount']:,.2f}*\n"
            
        await update.effective_message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in history_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to retrieve billing history.")

async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /report [dates|list] or /report [start_date] [end_date].
    Generates summary report.
    """
    try:
        show_dates = False
        start_date = None
        end_date = None
        
        if context.args:
            arg0 = context.args[0].lower()
            if arg0 in ("dates", "list"):
                show_dates = True
                if len(context.args) >= 2:
                    start_date = context.args[1]
                    end_date = context.args[2] if len(context.args) >= 3 else date.today().strftime("%Y-%m-%d")
            else:
                start_date = context.args[0]
                end_date = context.args[1] if len(context.args) >= 2 else date.today().strftime("%Y-%m-%d")
                show_dates = True
                
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                await update.effective_message.reply_text(
                    "❌ Invalid date format. Please use YYYY-MM-DD.\n"
                    "Usage: `/report` or `/report dates` or `/report 2026-06-01` or `/report 2026-06-01 2026-06-15`",
                    parse_mode="Markdown"
                )
                return
                
            report = db_service.get_report_for_range(start_date, end_date)
            bill_info = db_service.get_bill_for_range(start_date, end_date)
            entries = bill_info["entries"]
            
            msg = (
                f"📊 *Report for Range:* {start_date} to {end_date}\n\n"
                f"📈 Total Entries: *{report['total_entries']}*\n"
                f"🥛 Total Milk: *{report['total_liters']}L*\n"
                f"💵 *Bill Amount: ₹{report['bill_amount']:,.2f}*\n"
            )
            
            if show_dates and entries:
                msg += "\n*Entries Breakdown:*\n"
                for e in entries:
                    msg += f"• {e['entry_date']}: {e['liters']}L @ ₹{e['rate']:.1f}/L = ₹{e['cost']:.1f} (Cycle {e['cycle_number']})\n"
                    
            await update.effective_message.reply_text(msg, parse_mode="Markdown")
        else:
            report = db_service.get_report_data()
            
            msg = (
                "📊 *Billing Summary Report*\n\n"
                f"📈 Total Entries: *{report['total_entries']}*\n"
                f"🥛 Total Milk: *{report['total_liters']}L*\n"
                f"✅ Total Paid Cycles: *{report['total_paid_cycles']}*\n"
                f"🟢 Open Cycle ({report['open_cycle_number']}) Bill: *₹{report['open_cycle_amount']:,.2f}*\n"
                "───────────────────\n"
                f"💵 *Grand Total: ₹{report['grand_total']:,.2f}*"
            )
            
            if show_dates:
                open_cycle = db_service.get_open_cycle()
                bill_info = db_service.get_cycle_bill(open_cycle["id"])
                entries = bill_info["entries"]
                if entries:
                    msg += "\n\n*Open Cycle Entries Breakdown:*\n"
                    for e in entries:
                        msg += f"• {e['entry_date']}: {e['liters']}L @ ₹{e['rate']:.1f}/L = ₹{e['cost']:.1f}\n"
                        
            await update.effective_message.reply_text(msg, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in report_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to generate report.")

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.handlers.common import admin_only
from app.services import db_service

logger = logging.getLogger(__name__)

@admin_only
async def set_rate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /setrate <rate> [date]
    Sets the milk rate. Date defaults to today.
    """
    if not context.args:
        await update.effective_message.reply_text(
            "ℹ️ *Set Rate Usage:*\n\n"
            "To set the rate starting today, copy, edit, and send this:\n"
            "`/setrate 65`\n\n"
            "To set the rate starting on a past/specific date, copy, edit, and send this:\n"
            "`/setrate 65 2026-06-01`",
            parse_mode="Markdown"
        )
        return

    try:
        rate = float(context.args[0])
        if rate <= 0:
            await update.effective_message.reply_text("❌ Rate must be a positive number.")
            return
    except ValueError:
        await update.effective_message.reply_text("❌ Invalid rate value. Please enter a valid number.")
        return

    date_str = None
    if len(context.args) >= 2:
        date_str = context.args[1]
        try:
            # Validate format
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await update.effective_message.reply_text("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2026-06-14).")
            return

    try:
        effective_date = db_service.set_rate(rate, date_str)
        await update.effective_message.reply_text(
            f"✅ *Rate Updated*\n"
            f"Rate: ₹{rate:.2f}/L\n"
            f"Effective Date: {effective_date}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in set_rate_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ An error occurred while setting the rate. Please check logs.")

@admin_only
async def close_cycle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /close [start_date] [end_date]
    Closes the current billing cycle or a specific date range as PAID.
    """
    try:
        start_date = None
        end_date = None
        
        if context.args:
            if len(context.args) < 2:
                await update.effective_message.reply_text(
                    "❌ To close a range, please specify both start and end dates.\n"
                    "Usage: `/close <start_date> <end_date>` (e.g., `/close 2026-06-01 2026-06-10`)\n"
                    "Or `/close` to close the entire current open cycle.",
                    parse_mode="Markdown"
                )
                return
            start_date = context.args[0]
            end_date = context.args[1]
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                await update.effective_message.reply_text("❌ Invalid date format. Please use YYYY-MM-DD.")
                return

        if start_date:
            # Range-based close
            try:
                result = db_service.close_cycle_range(start_date, end_date)
                response = (
                    f"📄 *Invoice Closed for Range:* {start_date} to {end_date}\n\n"
                    f"Cycle: *{result['closed_cycle_number']}* (PAID)\n"
                    f"Milk: *{result['total_liters']}L*\n"
                    f"Amount: *₹{result['closed_bill_amount']:,.2f}*\n\n"
                    f"🚀 *Active Open Cycle:* {result['new_cycle_number']}"
                )
                await update.effective_message.reply_text(response, parse_mode="Markdown")
            except ValueError as ve:
                await update.effective_message.reply_text(f"❌ {ve}")
        else:
            # Traditional current cycle close
            open_cycle = db_service.get_open_cycle()
            cycle_id = open_cycle["id"]
            cycle_number = open_cycle["cycle_number"]
            
            bill_info = db_service.get_cycle_bill(cycle_id)
            total_liters = bill_info["total_liters"]
            bill_amount = bill_info["bill_amount"]
            
            if total_liters == 0:
                await update.effective_message.reply_text(
                    f"ℹ️ Current Cycle {cycle_number} has no milk entries. "
                    "You cannot close an empty cycle."
                )
                return
                
            result = db_service.close_current_cycle(cycle_id, bill_amount)
            
            response = (
                "📄 *Invoice Closed*\n\n"
                f"Cycle: *{result['closed_cycle_number']}*\n"
                f"Milk: *{total_liters}L*\n"
                f"Amount: *₹{result['closed_bill_amount']:,.2f}*\n\n"
                f"🚀 *New Cycle Started:* {result['new_cycle_number']}"
            )
            await update.effective_message.reply_text(response, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in close_cycle_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ Failed to close billing cycle. Please check logs.")

@admin_only
async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /delete [date]
    Prompts confirmation to delete the latest entry or a specific date entry.
    """
    try:
        # Check if date argument is provided
        date_str = None
        if context.args:
            date_str = context.args[0]
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                await update.effective_message.reply_text("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2026-06-13).")
                return

        if date_str:
            entry = db_service.get_today_entry(date_str)
            if not entry:
                await update.effective_message.reply_text(f"ℹ️ No entry found for date {date_str}.")
                return
            
            # Fetch cycle info for display
            cycle = db_service.get_cycle_for_date(date_str)
            cycle_number = cycle["cycle_number"]
            target_entry = {
                "id": entry["id"],
                "entry_date": entry["entry_date"],
                "liters": entry["liters"],
                "cycle_number": cycle_number
            }
        else:
            recent = db_service.get_recent_entries(limit=1)
            if not recent:
                await update.effective_message.reply_text("ℹ️ No milk entries found in database to delete.")
                return
            latest = recent[0]
            target_entry = {
                "id": latest["id"],
                "entry_date": latest["entry_date"],
                "liters": latest["liters"],
                "cycle_number": latest["cycle_number"]
            }

        msg = (
            "⚠️ *Confirm Deletion*\n\n"
            f"Are you sure you want to delete the entry for *{target_entry['entry_date']}*?\n\n"
            f"📅 Date: *{target_entry['entry_date']}*\n"
            f"🥛 Quantity: *{target_entry['liters']}L*\n"
            f"📦 Cycle: *{target_entry['cycle_number']}*\n\n"
            "💡 *Tip:* To delete a specific date entry, use: `/delete YYYY-MM-DD` (e.g. `/delete 2026-06-13`)"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"delete_confirm_{target_entry['id']}"),
                InlineKeyboardButton("❌ Cancel", callback_data="delete_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in delete_handler: {e}", exc_info=True)
        await update.effective_message.reply_text("❌ An error occurred. Please check logs.")

async def delete_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query handler for delete confirmation buttons."""
    query = update.callback_query
    await query.answer()
    
    # Verify the user is admin
    user = query.from_user
    from app.config import ADMIN_TELEGRAM_IDS
    if user.id not in ADMIN_TELEGRAM_IDS:
        await query.message.reply_text("⛔ You are not authorized to perform this action.")
        return
        
    data = query.data
    
    if data.startswith("delete_confirm_"):
        entry_id = int(data.split("_")[-1])
        try:
            # Delete by ID directly
            deleted = db_service.delete_entry_by_id(entry_id)
            if deleted:
                await query.edit_message_text(
                    f"✅ *Deleted Entry*\n\n"
                    f"📅 Date: {deleted['entry_date']}\n"
                    f"🥛 Quantity: {deleted['liters']}L",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Deletion failed: Entry not found or already deleted.")
        except Exception as e:
            logger.error(f"Error in delete_callback_handler: {e}", exc_info=True)
            await query.edit_message_text("❌ An error occurred during deletion.")
            
    elif data == "delete_cancel":
        await query.edit_message_text("❌ Deletion cancelled.")

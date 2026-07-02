import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from app.database.connection import get_db_cursor
from app.config import DEFAULT_RATE

logger = logging.getLogger(__name__)

def get_rate_for_date(date_str: str) -> float:
    """
    Returns the milk rate applicable on the given date (YYYY-MM-DD).
    The applicable rate is the one with the largest effective_date <= date_str.
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT rate_per_liter FROM settings 
                WHERE effective_date <= ? 
                ORDER BY effective_date DESC 
                LIMIT 1;
                """,
                (date_str,)
            )
            row = cursor.fetchone()
            if row:
                return float(row["rate_per_liter"])
            
            # If no rate is found (e.g. date is before 2000-01-01), fallback to oldest rate
            cursor.execute("SELECT rate_per_liter FROM settings ORDER BY effective_date ASC LIMIT 1;")
            row = cursor.fetchone()
            if row:
                return float(row["rate_per_liter"])
                
            return DEFAULT_RATE
    except Exception as e:
        logger.error(f"Error fetching rate for date {date_str}: {e}")
        return DEFAULT_RATE

def get_current_rate() -> float:
    """Returns the rate applicable today."""
    today_str = date.today().strftime("%Y-%m-%d")
    return get_rate_for_date(today_str)

def set_rate(rate: float, date_str: Optional[str] = None) -> str:
    """
    Sets the milk rate. If date_str is not provided, defaults to today.
    date_str should be in YYYY-MM-DD format.
    """
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")
    
    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Must be YYYY-MM-DD")
        
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO settings (rate_per_liter, effective_date)
            VALUES (?, ?)
            ON CONFLICT(effective_date) 
            DO UPDATE SET rate_per_liter = excluded.rate_per_liter;
            """,
            (rate, date_str)
        )
    return date_str

def get_cycle_for_date(date_str: str) -> Dict[str, Any]:
    """
    Finds the billing cycle matching the date.
    A cycle covers the period from its created_at date to its closed_at date (inclusive).
    If date_str is after the last closed cycle's closed_at, it belongs to the current OPEN cycle.
    If it is before the first cycle's created_at, it belongs to Cycle 1.
    """
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM billing_cycles ORDER BY cycle_number ASC;")
        cycles = [dict(row) for row in cursor.fetchall()]
        
    if not cycles:
        return get_open_cycle()
        
    # Convert date_str to date object
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format. Must be YYYY-MM-DD")
    
    for i, cycle in enumerate(cycles):
        created_date_str = cycle["created_at"].split()[0]
        created_date = datetime.strptime(created_date_str, "%Y-%m-%d").date()
        
        closed_date = None
        if cycle["closed_at"]:
            closed_date_str = cycle["closed_at"].split()[0]
            closed_date = datetime.strptime(closed_date_str, "%Y-%m-%d").date()
            
        if closed_date and target_date <= closed_date:
            if target_date >= created_date:
                return cycle
            if i == 0:
                return cycle
                
    return get_open_cycle()

def get_open_cycle() -> Dict[str, Any]:
    """Gets the currently OPEN billing cycle, auto-creating one if missing."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM billing_cycles WHERE status = 'OPEN' ORDER BY cycle_number DESC LIMIT 1;")
        row = cursor.fetchone()
        if row:
            return dict(row)
            
        # Fallback: create cycle 1 if none found
        cursor.execute("SELECT MAX(cycle_number) as max_num FROM billing_cycles;")
        max_row = cursor.fetchone()
        next_num = (max_row["max_num"] or 0) + 1
        
        cursor.execute(
            "INSERT INTO billing_cycles (cycle_number, status, created_at) VALUES (?, ?, ?);",
            (next_num, "OPEN", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        cursor.execute("SELECT * FROM billing_cycles WHERE status = 'OPEN' ORDER BY cycle_number DESC LIMIT 1;")
        return dict(cursor.fetchone())

def create_milk_entry(date_str: str, liters: float, cycle_id: int) -> Dict[str, Any]:
    """Adds or updates a milk entry. Overwrites if entry for entry_date already exists."""
    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Must be YYYY-MM-DD")
        
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO milk_entries (entry_date, liters, cycle_id, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(entry_date) 
            DO UPDATE SET liters = excluded.liters, cycle_id = excluded.cycle_id;
            """,
            (date_str, liters, cycle_id)
        )
        cursor.execute("SELECT * FROM milk_entries WHERE entry_date = ?;", (date_str,))
        return dict(cursor.fetchone())

def get_today_entry(date_str: str) -> Optional[Dict[str, Any]]:
    """Returns the entry for a specific date, if it exists."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM milk_entries WHERE entry_date = ?;", (date_str,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_recent_entries(limit: int = 10) -> List[Dict[str, Any]]:
    """Returns recent milk entries with their cycle numbers."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT me.*, bc.cycle_number 
            FROM milk_entries me 
            JOIN billing_cycles bc ON me.cycle_id = bc.id 
            ORDER BY me.entry_date DESC 
            LIMIT ?;
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

def get_cycle_bill(cycle_id: int) -> Dict[str, Any]:
    """
    Calculates the bill for a cycle by getting all entries and applying 
    the rate applicable on each entry's date.
    """
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT id, cycle_number, status, created_at, closed_at, billed_amount FROM billing_cycles WHERE id = ?;",
            (cycle_id,)
        )
        cycle_row = cursor.fetchone()
        if not cycle_row:
            return {"total_liters": 0.0, "bill_amount": 0.0, "entries": []}
            
        cycle = dict(cycle_row)
        
        # Fetch entries
        cursor.execute(
            "SELECT * FROM milk_entries WHERE cycle_id = ? ORDER BY entry_date ASC;",
            (cycle_id,)
        )
        entries = [dict(row) for row in cursor.fetchall()]
        
        total_liters = 0.0
        bill_amount = 0.0
        detailed_entries = []
        
        for entry in entries:
            liters = entry["liters"]
            entry_date = entry["entry_date"]
            rate = get_rate_for_date(entry_date)
            cost = liters * rate
            
            total_liters += liters
            bill_amount += cost
            
            detailed_entries.append({
                "entry_date": entry_date,
                "liters": liters,
                "rate": rate,
                "cost": cost
            })
            
        return {
            "cycle_id": cycle["id"],
            "cycle_number": cycle["cycle_number"],
            "status": cycle["status"],
            "total_liters": total_liters,
            "bill_amount": round(bill_amount, 2),
            "entries": detailed_entries
        }

def close_current_cycle(cycle_id: int, bill_amount: float) -> Dict[str, Any]:
    """
    Marks the current cycle as PAID with the calculated bill amount, 
    and opens a new cycle.
    """
    with get_db_cursor() as cursor:
        # Get current cycle details
        cursor.execute("SELECT cycle_number FROM billing_cycles WHERE id = ?;", (cycle_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Cycle with ID {cycle_id} not found")
        current_cycle_number = row["cycle_number"]
        
        # Close current cycle
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            UPDATE billing_cycles 
            SET status = 'PAID', closed_at = ?, billed_amount = ? 
            WHERE id = ?;
            """,
            (now_str, bill_amount, cycle_id)
        )
        
        # Open new cycle
        new_cycle_number = current_cycle_number + 1
        cursor.execute(
            "INSERT INTO billing_cycles (cycle_number, status, created_at) VALUES (?, 'OPEN', ?);",
            (new_cycle_number, now_str)
        )
        
        cursor.execute("SELECT id FROM billing_cycles WHERE status = 'OPEN' ORDER BY cycle_number DESC LIMIT 1;")
        new_cycle_id = cursor.fetchone()["id"]
        
        return {
            "closed_cycle_number": current_cycle_number,
            "closed_bill_amount": bill_amount,
            "new_cycle_number": new_cycle_number,
            "new_cycle_id": new_cycle_id
        }

def get_cycle_history() -> List[Dict[str, Any]]:
    """
    Returns history of all cycles. 
    For PAID cycles, returns stored billed_amount. 
    For the OPEN cycle, calculates the current bill dynamically.
    """
    history = []
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM billing_cycles ORDER BY cycle_number ASC;")
        cycles = [dict(row) for row in cursor.fetchall()]
        
    for cycle in cycles:
        if cycle["status"] == "PAID":
            history.append({
                "cycle_number": cycle["cycle_number"],
                "status": cycle["status"],
                "billed_amount": cycle["billed_amount"] or 0.0
            })
        else:
            bill_info = get_cycle_bill(cycle["id"])
            history.append({
                "cycle_number": cycle["cycle_number"],
                "status": cycle["status"],
                "billed_amount": bill_info["bill_amount"]
            })
            
    return history

def get_report_data() -> Dict[str, Any]:
    """Generates full billing summary report statistics."""
    with get_db_cursor() as cursor:
        # Total entries
        cursor.execute("SELECT COUNT(*) as count, SUM(liters) as total_liters FROM milk_entries;")
        summary = cursor.fetchone()
        total_entries = summary["count"] or 0
        total_liters = summary["total_liters"] or 0.0
        
        # Total paid cycles count and paid amount sum
        cursor.execute("SELECT COUNT(*) as count, SUM(billed_amount) as total_paid FROM billing_cycles WHERE status = 'PAID';")
        paid_summary = cursor.fetchone()
        total_paid_cycles = paid_summary["count"] or 0
        total_paid_amount = paid_summary["total_paid"] or 0.0
        
    # Open cycle details
    open_cycle = get_open_cycle()
    open_cycle_bill = get_cycle_bill(open_cycle["id"])
    open_cycle_amount = open_cycle_bill["bill_amount"]
    
    grand_total = total_paid_amount + open_cycle_amount
    
    return {
        "total_entries": total_entries,
        "total_liters": round(total_liters, 2),
        "total_paid_cycles": total_paid_cycles,
        "open_cycle_number": open_cycle["cycle_number"],
        "open_cycle_amount": round(open_cycle_amount, 2),
        "grand_total": round(grand_total, 2)
    }

def delete_latest_entry() -> Optional[Dict[str, Any]]:
    """Deletes the latest milk entry. Returns details of deleted entry or None."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM milk_entries ORDER BY entry_date DESC LIMIT 1;")
        latest = cursor.fetchone()
        if not latest:
            return None
            
        latest_dict = dict(latest)
        cursor.execute("DELETE FROM milk_entries WHERE id = ?;", (latest_dict["id"],))
        return latest_dict

def delete_entry_by_date(date_str: str) -> Optional[Dict[str, Any]]:
    """Deletes the milk entry for a specific date. Returns details of deleted entry or None."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM milk_entries WHERE entry_date = ?;", (date_str,))
        row = cursor.fetchone()
        if not row:
            return None
            
        entry_dict = dict(row)
        cursor.execute("DELETE FROM milk_entries WHERE id = ?;", (entry_dict["id"],))
        return entry_dict

def delete_entry_by_id(entry_id: int) -> Optional[Dict[str, Any]]:
    """Deletes a milk entry by its database ID. Returns details of deleted entry or None."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM milk_entries WHERE id = ?;", (entry_id,))
        row = cursor.fetchone()
        if not row:
            return None
            
        entry_dict = dict(row)
        cursor.execute("DELETE FROM milk_entries WHERE id = ?;", (entry_id,))
        return entry_dict


def get_bill_for_range(start_date: str, end_date: str) -> Dict[str, Any]:
    """Calculates bill details for a specific date range, spanning any cycles."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT me.*, bc.cycle_number 
            FROM milk_entries me
            JOIN billing_cycles bc ON me.cycle_id = bc.id
            WHERE me.entry_date BETWEEN ? AND ? 
            ORDER BY me.entry_date ASC;
            """,
            (start_date, end_date)
        )
        entries = [dict(row) for row in cursor.fetchall()]
        
    total_liters = 0.0
    bill_amount = 0.0
    detailed_entries = []
    
    for entry in entries:
        liters = entry["liters"]
        entry_date = entry["entry_date"]
        rate = get_rate_for_date(entry_date)
        cost = liters * rate
        
        total_liters += liters
        bill_amount += cost
        
        detailed_entries.append({
            "entry_date": entry_date,
            "liters": liters,
            "rate": rate,
            "cost": cost,
            "cycle_number": entry["cycle_number"]
        })
        
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_liters": total_liters,
        "bill_amount": round(bill_amount, 2),
        "entries": detailed_entries
    }

def get_report_for_range(start_date: str, end_date: str) -> Dict[str, Any]:
    """Generates stats summary for a specific date range."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) as count, SUM(liters) as total_liters 
            FROM milk_entries 
            WHERE entry_date BETWEEN ? AND ?;
            """,
            (start_date, end_date)
        )
        summary = cursor.fetchone()
        total_entries = summary["count"] or 0
        total_liters = summary["total_liters"] or 0.0
        
    bill_info = get_bill_for_range(start_date, end_date)
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_entries": total_entries,
        "total_liters": round(total_liters, 2),
        "bill_amount": bill_info["bill_amount"]
    }

def close_cycle_range(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Closes a specific date range as PAID.
    - If the range covers the start of the current open cycle:
      We close the current open cycle (mark it PAID) with the range's bill,
      create a new OPEN cycle, and move any entries after the range to the new OPEN cycle.
    - Otherwise (e.g. closing a range in the middle or past):
      We create a new PAID cycle, move the range's entries to it,
      and leave the current OPEN cycle open.
    """
    # 1. Calculate bill for the range
    bill_info = get_bill_for_range(start_date, end_date)
    bill_amount = bill_info["bill_amount"]
    total_liters = bill_info["total_liters"]
    entries = bill_info["entries"]
    
    if not entries:
        raise ValueError(f"No entries found in range {start_date} to {end_date}")
        
    with get_db_cursor() as cursor:
        # Get current open cycle details
        open_cycle = get_open_cycle()
        open_cycle_id = open_cycle["id"]
        open_cycle_number = open_cycle["cycle_number"]
        
        # Get min entry date in the current open cycle
        cursor.execute("SELECT MIN(entry_date) as min_date FROM milk_entries WHERE cycle_id = ?;", (open_cycle_id,))
        min_row = cursor.fetchone()
        min_date_in_open = min_row["min_date"]
        
        # Determine if we cover the start of the open cycle
        covers_start = False
        if min_date_in_open:
            covers_start = (start_date <= min_date_in_open)
            
        if covers_start:
            # Case 1: Range covers the start. We can close the current open cycle
            # and create a new open cycle for the remaining entries.
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                UPDATE billing_cycles 
                SET status = 'PAID', closed_at = ?, billed_amount = ? 
                WHERE id = ?;
                """,
                (now_str, bill_amount, open_cycle_id)
            )
            
            # Create new OPEN cycle
            new_cycle_number = open_cycle_number + 1
            cursor.execute(
                "INSERT INTO billing_cycles (cycle_number, status, created_at) VALUES (?, 'OPEN', ?);",
                (new_cycle_number, now_str)
            )
            cursor.execute("SELECT id FROM billing_cycles WHERE status = 'OPEN' ORDER BY cycle_number DESC LIMIT 1;")
            new_cycle_id = cursor.fetchone()["id"]
            
            # Move entries after end_date to the new OPEN cycle
            cursor.execute(
                "UPDATE milk_entries SET cycle_id = ? WHERE cycle_id = ? AND entry_date > ?;",
                (new_cycle_id, open_cycle_id, end_date)
            )
            
            # Move entries before start_date to the new OPEN cycle (if any, though covers_start means there should be none)
            cursor.execute(
                "UPDATE milk_entries SET cycle_id = ? WHERE cycle_id = ? AND entry_date < ?;",
                (new_cycle_id, open_cycle_id, start_date)
            )
            
            return {
                "closed_cycle_number": open_cycle_number,
                "closed_bill_amount": bill_amount,
                "total_liters": total_liters,
                "new_cycle_number": new_cycle_number,
                "is_sequential": True
            }
        else:
            # Case 2: Range does not cover the start.
            # We create a new PAID cycle and move only the range's entries to it.
            cursor.execute("SELECT MAX(cycle_number) as max_num FROM billing_cycles;")
            max_row = cursor.fetchone()
            new_cycle_number = (max_row["max_num"] or 0) + 1
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO billing_cycles (cycle_number, status, created_at, closed_at, billed_amount)
                VALUES (?, 'PAID', ?, ?, ?);
                """,
                (new_cycle_number, now_str, now_str, bill_amount)
            )
            cursor.execute("SELECT id FROM billing_cycles WHERE cycle_number = ?;", (new_cycle_number,))
            new_cycle_id = cursor.fetchone()["id"]
            
            # Move the entries in the range to the new PAID cycle
            cursor.execute(
                "UPDATE milk_entries SET cycle_id = ? WHERE entry_date BETWEEN ? AND ?;",
                (new_cycle_id, start_date, end_date)
            )
            
            return {
                "closed_cycle_number": new_cycle_number,
                "closed_bill_amount": bill_amount,
                "total_liters": total_liters,
                "new_cycle_number": open_cycle_number, # The current open cycle remains unchanged
                "is_sequential": False
            }



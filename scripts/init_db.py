import os
import sys
import logging
from datetime import datetime

# Allow importing from the root app folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_db_cursor
from app.config import DEFAULT_RATE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("init_db")

def init_db():
    logger.info("Initializing SQLite database...")
    
    with get_db_cursor() as cursor:
        # 1. Create settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rate_per_liter REAL NOT NULL,
                effective_date TEXT NOT NULL UNIQUE
            );
        """)
        
        # 2. Create billing_cycles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_number INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK (status IN ('OPEN', 'PAID')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                billed_amount REAL
            );
        """)
        
        # 3. Create milk_entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS milk_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL UNIQUE,
                liters REAL NOT NULL,
                cycle_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cycle_id) REFERENCES billing_cycles(id)
            );
        """)
        
        # Seed default rate if settings is empty
        cursor.execute("SELECT COUNT(*) as count FROM settings;")
        if cursor.fetchone()["count"] == 0:
            logger.info(f"Seeding default milk rate: {DEFAULT_RATE} effective from 2000-01-01")
            cursor.execute(
                "INSERT INTO settings (rate_per_liter, effective_date) VALUES (?, ?);",
                (DEFAULT_RATE, "2000-01-01")
            )
            
        # Seed first billing cycle if billing_cycles is empty
        cursor.execute("SELECT COUNT(*) as count FROM billing_cycles;")
        if cursor.fetchone()["count"] == 0:
            logger.info("Seeding initial billing cycle (Cycle 1 - OPEN)")
            cursor.execute(
                "INSERT INTO billing_cycles (cycle_number, status, created_at) VALUES (?, ?, ?);",
                (1, "OPEN", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            
    logger.info("Database initialization completed successfully.")

if __name__ == "__main__":
    init_db()

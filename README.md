# Telegram Milk Billing Bot

A production-ready Telegram bot built with Python 3.12+, `python-telegram-bot`, and SQLite. Designed for tracking daily milk entries and managing billing cycles dynamically. It features granular, date-based milk rate settings and is ready for immediate deployment as an always-on task on PythonAnywhere.

---

## Features

- **Daily Milk Tracking**: Record milk quantities in liters (e.g. `10` or `/entry 10` for today's date).
- **Date-Based Historical Rates**: Set milk rates on specific dates. The bot dynamically applies the rate effective on the date of each entry, resolving retroactive billing issues.
- **Dynamic Billing Cycles**: Keep track of milk entries under billing cycles. Only one cycle is `OPEN` at a time.
- **Admin Authentication**: Restricts billing closure, rate updates, and entries deletion to the administrator's Telegram ID.
- **Interactive Deletion**: Deletes the latest entry using Telegram Inline Keyboard confirmations.
- **Summary Reports**: Generate instant statistics on total entries, total milk quantity, paid cycles, current open cycle bill, and grand total.
- **Robust SQLite Backend**: Single-file relational storage with full integrity checks and foreign key constraints.
- **Structured Logging**: Clean stdout logging coupled with rotating logs written to `logs/milk_bot.log`.

---

## Database Schema

The bot uses SQLite with three tables:

### 1. `settings`
Stores milk rates per liter along with their effective dates.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `rate_per_liter` (REAL NOT NULL)
- `effective_date` (TEXT NOT NULL UNIQUE) - *Format: YYYY-MM-DD*

### 2. `billing_cycles`
Tracks closed and open billing cycles.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `cycle_number` (INTEGER NOT NULL UNIQUE)
- `status` (TEXT NOT NULL CHECK(status IN ('OPEN', 'PAID')))
- `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
- `closed_at` (TIMESTAMP)
- `billed_amount` (REAL) - *Stores the finalized cycle bill at the moment of closure*

### 3. `milk_entries`
Tracks individual daily milk entries.
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `entry_date` (TEXT NOT NULL UNIQUE) - *Format: YYYY-MM-DD (One entry per day)*
- `liters` (REAL NOT NULL)
- `cycle_id` (INTEGER NOT NULL, FOREIGN KEY to `billing_cycles(id)`)
- `created_at` (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)

---

## Bot Commands

### User Commands
- `/start` - Greeting and quick guide.
- `/help` - Display all available commands.
- `/rate` - View the current milk rate (applicable today).
- `/entry <liters> [YYYY-MM-DD]` - Add or modify a milk entry. If the date is omitted, it defaults to today (e.g., `/entry 10` or `/entry 12 2026-06-13`). Submitting a new value for an existing date will overwrite the old value and show the change (e.g., `10L ➔ 12L`).
- **Plain Entry** - Sending just a number (e.g. `10` or `12.5`) or a number followed by a date (e.g. `10 2026-06-13`) is parsed exactly as `/entry`.
- `/today` - View today's recorded milk entry.
- `/entries` - Show the last 10 milk entries.
- `/bill [dates|list]` or `/bill [start_date] [end_date]` - Calculate bill for the active `OPEN` cycle (default) or a specific date range. Append `dates` or `list` to view a detailed breakdown of all dates and rates (e.g., `/bill list` or `/bill 2026-06-01 2026-06-15`).
- `/history` - View the status and amounts of past and present billing cycles.
- `/report [dates|list]` or `/report [start_date] [end_date]` - Show high-level summary report for all time (default) or a specific date range. Append `dates` or `list` to see the breakdown of individual entries.

### Admin Commands (Admin Only)
- `/setrate <rate> [YYYY-MM-DD]` - Sets a new rate. If the date is omitted, it defaults to today. It applies to all entries on or after that date.
- `/close [start_date] [end_date]` - Closes the current open cycle (if no arguments are specified) or a specific date range as PAID. Any remaining entries before or after the range in the current cycle are safely preserved in the open cycle.
- `/delete [YYYY-MM-DD]` - Prompts a secure interactive confirmation to delete the latest entry (if no date is provided) or the entry for a specific date (e.g. `/delete 2026-06-13`).

---

## Local Development and Setup

### Prerequisites
- Python 3.12+
- `uv` Package Manager (Fast Python packaging tool)

### 1. Install `uv` (If not installed)
**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Project Dependencies
Use `uv` to create a virtual environment and sync packages. On Windows, use `--link-mode copy` if you experience filesystem linking permission issues:
```bash
# Clone or move to the project directory
cd D:/PythonTools/milk

# Install dependencies (automatically creates .venv)
uv add python-telegram-bot python-dotenv --link-mode copy
```

### 3. Configuration Setup
Create a `.env` file in the root directory (or update the existing one):
```ini
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id
DEFAULT_RATE=65
DATABASE_PATH=data/milk.db
```
*Note: You can obtain a `BOT_TOKEN` by messaging `@BotFather` on Telegram. Your personal Telegram ID can be found using bots like `@userinfobot`.*

### 4. Running the Bot
The startup runner will automatically initialize the database on its first execution.
```bash
uv run main.py
```

---

## PythonAnywhere Deployment Guide

Deploying the bot as a background task on [PythonAnywhere](https://www.pythonanywhere.com/) is quick and straightforward:

### 1. Upload Project Files
1. Compress your project folder into a `.zip` file (exclude `.venv`, `data/`, and `logs/`).
2. Log into PythonAnywhere, go to the **Files** tab, and upload your `.zip` file to `/home/<your-username>/`.
3. Open a **Bash Console** from your PythonAnywhere dashboard and extract the archive:
   ```bash
   unzip project.zip -d milk-bot
   cd milk-bot
   ```

### 2. Install Dependencies using `uv`
Run these commands in the PythonAnywhere Bash Console to setup `uv` and install dependencies:
```bash
# Install uv locally in your user profile
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

# Create a virtual environment using python 3.12
uv venv --python 3.12

# Activate virtual environment
source .venv/bin/activate

# Install requirements
uv pip install python-telegram-bot python-dotenv
```

### 3. Setup Environment Variables
Create a `.env` file in the project folder `/home/<your-username>/milk-bot/` using the file editor or console:
```bash
nano .env
```
Add your configurations:
```ini
BOT_TOKEN=your_telegram_bot_token
ADMIN_TELEGRAM_ID=your_telegram_id
DEFAULT_RATE=65
DATABASE_PATH=data/milk.db
```
Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 4. Initialize the Database
Run the database initializer script to set up schema tables and seed values:
```bash
python scripts/init_db.py
```
This creates the SQLite database at `/home/<your-username>/milk-bot/data/milk.db`.

### 5. Deployment Options (Free vs. Paid Accounts)

#### Option A: Web App + Webhook (For FREE PythonAnywhere accounts)
Since Always-On tasks are a paid feature on PythonAnywhere, free users can run the bot indefinitely as a Web App using Webhooks. When Telegram receives an update, it sends an HTTP POST request which wakes up your PythonAnywhere web app automatically.

1. **Update `.env`**: Add your PythonAnywhere web app URL to `.env`:
   ```ini
   WEBHOOK_URL=https://<your-username>.pythonanywhere.com
   ```
2. **Install Flask**: Ensure Flask is installed in your virtual environment:
   ```bash
   uv pip install flask
   ```
3. **Register Webhook**: Run the helper script to tell Telegram to send updates to your PythonAnywhere site:
   ```bash
   python scripts/set_webhook.py
   ```
4. **Create PythonAnywhere Web App**:
   - Go to the **Web** tab on the PythonAnywhere dashboard.
   - Click **Add a new web app**.
   - Click **Next**, choose **Manual Configuration** (do NOT choose Flask directly), and select **Python 3.12**.
5. **Configure WSGI File**:
   - On the **Web** tab, click the link to edit the **WSGI configuration file** (located under *Code* section).
   - Delete all contents of the file and paste this configuration (replace `<username>` with your PythonAnywhere username):
     ```python
     import sys
     import os

     path = '/home/<username>/milk-bot'
     if path not in sys.path:
         sys.path.append(path)

     # Load environment variables
     from dotenv import load_dotenv
     load_dotenv(os.path.join(path, '.env'))

     # Import the Flask app object as 'application'
     from main import flask_app as application
     ```
   - Click **Save** and then **Reload** your web app from the Web tab.

---

#### Option B: Always-On Task (For PAID PythonAnywhere accounts)
If you have a paid PythonAnywhere account, you can run the bot in polling mode continuously:

1. Navigate to the **Tasks** tab on the PythonAnywhere dashboard.
2. In the **Always-On Tasks** section, input the following command (replace `<username>` with your username):
   ```bash
   /home/<username>/milk-bot/.venv/bin/python /home/<username>/milk-bot/main.py
   ```
3. Click **Create**.

---

## Maintenance and Operations

### Restarting the Bot
- **Webhook Mode (Free):** Go to the **Web** tab on PythonAnywhere and click the green **Reload <your-domain>** button.
- **Polling Mode (Paid):** Go to the **Tasks** tab and click the **Restart** button next to your Always-on task.
- **Locally:** Simply press `Ctrl+C` in your terminal and rerun `uv run main.py`.

### SQLite Database Backup and Restore
Since SQLite stores everything in a single file (`data/milk.db`), backups are trivial.

#### Backup Command (Manual/Cron)
Copy the database file to a safe backup directory:
```bash
mkdir -p backups
cp data/milk.db backups/milk_backup_$(date +%Y%m%d_%H%M%S).db
```
*Tip: On PythonAnywhere, you can schedule this command as a daily or weekly job in the **Scheduled Tasks** tab.*

#### Restore Command
To restore from a backup:
1. Stop the bot (disable/stop Always-On Task on PythonAnywhere).
2. Copy the backup file over the active database:
   ```bash
   cp backups/milk_backup_YYYYMMDD_HHMMSS.db data/milk.db
   ```
3. Restart the bot.

---

## Error Recovery Instructions

### 1. Database Lock Errors (`database is locked`)
- **Cause:** Multiple write processes attempting to access SQLite simultaneously.
- **Fix:** SQLite handles concurrent reads, but writes require exclusive locks. The bot is designed to run in a single process. Ensure only one instance of the bot is running.
  - On PythonAnywhere, check that you do not have another console running `main.py` when your Always-On task is active. Kill orphan processes if necessary:
    ```bash
    pkill -f main.py
    ```

### 2. Unauthorized Admin Access
- **Cause:** The `ADMIN_TELEGRAM_ID` environment variable does not match your Telegram user ID.
- **Fix:** Send `/start` to your bot. If it behaves as a non-admin, find your exact ID (using `@userinfobot`) and update your `.env` file, then restart the bot.

### 3. Missing/Recreated Virtual Environments
- If dependencies get corrupted:
  ```bash
  rm -rf .venv
  uv venv --python 3.12
  uv pip install python-telegram-bot python-dotenv
  ```

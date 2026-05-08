#!/bin/bash
# ============================================================
# install.sh — One-time setup for the weather bot on Ubuntu VPS
# Run once after uploading the files to your server:
#   bash install.sh
# ============================================================

set -e

echo "=== Weather Bot — VPS Setup ==="

# 1. Update system packages
echo "[1/5] Updating system packages..."
sudo apt-get update -q && sudo apt-get upgrade -y -q

# 2. Install Python 3.11+ and pip
echo "[2/5] Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# 3. Create a virtual environment
echo "[3/5] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Python dependencies
echo "[4/5] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Create .env from example (if not already present)
echo "[5/5] Setting up config..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "  ✅ .env file created."
    echo "  👉 Edit it now:  nano .env"
    echo "     Fill in your API keys before running the bot."
else
    echo "  .env already exists — skipping."
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit your API keys:    nano .env"
echo "  2. Test the bot:          source venv/bin/activate && python weather_bot.py --dry-run"
echo "  3. Add cron jobs:         crontab -e   (see crontab.txt for the schedule)"
echo ""
